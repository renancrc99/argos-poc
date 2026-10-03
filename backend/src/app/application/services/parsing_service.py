"""Serviço de parsing de documentos. Extrai texto puro de diferentes formatos."""

import re
import unicodedata

import fitz  # PyMuPDF
from docx import Document as DocxDocument

import structlog
from app.domain.exceptions import DocumentParsingError

logger = structlog.get_logger()

# Tabela de mojibake: sequências multibyte UTF-8 decodificadas byte a byte como Latin-1.
# Byte 0x80 em Latin-1 = U+0080 (caractere de controle C1), NÃO é o símbolo de Euro.
# Precisa ser aplicado ANTES de remover os caracteres de controle.
_MOJIBAKE = [
    # Interpretação Latin-1 (fitz decodifica bytes UTF-8 como code points Latin-1 individuais)
    ("\u00e2\u0080\u009c", '"'),   # 0xE2 0x80 0x9C → " (aspas duplas de abertura)
    ("\u00e2\u0080\u009d", '"'),   # 0xE2 0x80 0x9D → " (aspas duplas de fechamento)
    ("\u00e2\u0080\u0099", "'"),   # 0xE2 0x80 0x99 → ' (aspas simples de fechamento)
    ("\u00e2\u0080\u0098", "'"),   # 0xE2 0x80 0x98 → ' (aspas simples de abertura)
    ("\u00e2\u0080\u0094", "--"),  # 0xE2 0x80 0x94 → — (travessão longo)
    ("\u00e2\u0080\u0093", "-"),   # 0xE2 0x80 0x93 → – (travessão curto)
    ("\u00e2\u0080\u00a6", "..."), # 0xE2 0x80 0xA6 → … (reticências)
    ("\u00e2\u0080\u00a2", "*"),   # 0xE2 0x80 0xA2 → • (marcador de lista)
    # Interpretação Windows-1252 (byte 0x80 = símbolo de Euro U+20AC em Win-1252)
    ("\u00e2\u20ac\u2122", "'"),   # â€™ → '
    ("\u00e2\u20ac\u02dc", "'"),   # â€˜ → '
    ("\u00e2\u20ac\u0153", '"'),   # â€œ → "
    ("\u00e2\u20ac\u009d", '"'),   # â€ → "
    ("\u00e2\u20ac\u201c", "--"),  # â€" → travessão longo
    ("\u00e2\u20ac\u201d", "-"),   # â€" → travessão curto
    ("\u00e2\u20ac\u00a6", "..."), # â€¦ → reticências
]


def _clean_text(text: str) -> str:
    """Normaliza o texto extraído: corrige artefatos de codificação, achata quebras de linha, colapsa espaços."""
    # 1. Corrige as sequências de 3 caracteres de mojibake PRIMEIRO (antes de remover chars de controle)
    for bad, good in _MOJIBAKE:
        text = text.replace(bad, good)
    # 2. Expande caracteres de compatibilidade: ﬁ→fi, ﬂ→fl, ﬀ→ff, etc.
    text = unicodedata.normalize("NFKC", text)
    # 3. Remove chars de controle C0/C1 (seguro agora que as sequências de mojibake já foram trocadas)
    text = re.sub(r"[\ufffd\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]", " ", text)
    # 4. Fallback para PDFs que mapeiam aspas curvas direto para â (U+00E2) via tabela ToUnicode.
    #    Troca â isolado (fora de uma palavra) por aspas retas.
    #    Seguro para texto em inglês — nenhuma palavra real do inglês contém â.
    text = re.sub(r"(?<!\w)\u00e2(?!\w)", '"', text)
    # 5. Achata quebras de linha em espaços
    text = text.replace("\n", " ")
    # 6. Colapsa múltiplos espaços em um só
    text = re.sub(r" {2,}", " ", text)
    return text.strip()


class ParsingService:
    """Extrai texto de PDF, DOCX, TXT e MD."""

    def extract_text(self, file_data: bytes, content_type: str, filename: str) -> list[dict]:
        """
        Extrai texto do arquivo.
        Retorna lista de dicts: [{"text": "...", "page": 1, "source": "file.pdf"}, ...]
        """
        match content_type:
            case "application/pdf":
                return self._parse_pdf(file_data, filename)
            case "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
                return self._parse_docx(file_data, filename)
            case "text/plain" | "text/markdown":
                return self._parse_text(file_data, filename)
            case _:
                logger.warning("unsupported_content_type", content_type=content_type)
                return self._parse_text(file_data, filename)

    def _parse_pdf(self, data: bytes, filename: str) -> list[dict]:
        # ── Abre o arquivo ────────────────────────────────────────────────────
        try:
            doc = fitz.open(stream=data, filetype="pdf")
        except Exception as exc:
            raise DocumentParsingError(
                filename,
                f"não foi possível abrir o arquivo ({exc}). "
                "Verifique se o arquivo não está corrompido ou em um formato não suportado.",
            ) from exc

        pages = []
        with doc:
            # ── Criptografado / protegido por senha ─────────────────────────────
            if doc.is_encrypted:
                # Tenta senha vazia primeiro (alguns PDFs são "criptografados" mas abrem sem senha)
                if not doc.authenticate(""):
                    raise DocumentParsingError(
                        filename,
                        "o arquivo está protegido por senha — remova a proteção antes de ingerir.",
                    )

            # ── Extrai o texto de cada página ────────────────────────────────
            for page_num, page in enumerate(doc, start=1):
                try:
                    raw = page.get_text(flags=fitz.TEXT_DEHYPHENATE).strip()
                except Exception:
                    # Fallback: algumas páginas quebram com a flag de dehyphenate
                    try:
                        raw = page.get_text().strip()
                    except Exception:
                        raw = ""
                text = _clean_text(raw)
                if text:
                    pages.append({"text": text, "page": page_num, "source": filename})

        # ── Nenhum texto encontrado ──────────────────────────────────────────────
        if not pages:
            raise DocumentParsingError(
                filename,
                "nenhum texto extraível encontrado — o PDF pode ser baseado em imagens "
                "digitalizadas (scanned) e precisar de OCR, ou todas as páginas estão em branco.",
            )

        logger.info("pdf_parsed", filename=filename, pages=len(pages))
        return pages

    def _parse_docx(self, data: bytes, filename: str) -> list[dict]:
        import io
        doc = DocxDocument(io.BytesIO(data))
        full_text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        logger.info("docx_parsed", filename=filename, chars=len(full_text))
        return [{"text": full_text, "page": None, "source": filename}]

    def _parse_text(self, data: bytes, filename: str) -> list[dict]:
        text = data.decode("utf-8", errors="replace").strip()
        logger.info("text_parsed", filename=filename, chars=len(text))
        return [{"text": text, "page": None, "source": filename}]
