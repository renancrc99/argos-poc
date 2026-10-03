import { useState } from "react";
import type { ChatMessage } from "../../types/chat";

interface Props {
  message: ChatMessage;
}

export function MessageBubble({ message }: Props) {
  const [sourcesOpen, setSourcesOpen] = useState(false);
  const isUser = message.role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div className={`max-w-[75%] ${isUser ? "items-end" : "items-start"} flex flex-col gap-1`}>
        <div
          className={`px-4 py-2.5 rounded-2xl text-sm leading-relaxed ${
            isUser
              ? "bg-primary-600 text-white rounded-br-sm"
              : "bg-white text-gray-900 shadow-sm border border-gray-200 rounded-bl-sm"
          }`}
        >
          {message.content}
        </div>

        {!isUser && message.sources && message.sources.length > 0 && (
          <div className="ml-1">
            <button
              onClick={() => setSourcesOpen((o) => !o)}
              className="text-xs text-primary-600 hover:underline"
            >
              {sourcesOpen ? "Ocultar fontes" : `${message.sources.length} fonte(s)`}
            </button>
            {sourcesOpen && (
              <ul className="mt-1 space-y-1">
                {message.sources.map((s, i) => (
                  <li key={i} className="text-xs text-gray-500 bg-gray-50 rounded px-2 py-1">
                    <span className="font-medium text-gray-700">{s.source}</span>
                    {s.page != null && <span> · p.{s.page}</span>}
                    <span className="ml-1 text-gray-400">score {s.score.toFixed(2)}</span>
                    <p className="mt-0.5 text-gray-400 italic line-clamp-2">{s.snippet}</p>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
