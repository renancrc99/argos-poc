/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        // Paleta "Arsenal" — cor primária (era azul; vermelho oficial do Arsenal
        // em primary-600, mesma posição de peso que os usos antigos de blue-600)
        primary: {
          50: "#FFF1F0",
          100: "#FFE1DE",
          200: "#FFC3BC",
          300: "#FF9186",
          400: "#FA5445",
          500: "#F41F0F",
          600: "#EF0107",
          700: "#C50106",
          800: "#9C0105",
          900: "#730004",
        },
        // Azul-marinho do Arsenal — acento secundário, uso pontual
        secondary: "#0A3D75",
      },
      fontFamily: {
        logo: ["Cinzel", "Georgia", "serif"],
      },
      keyframes: {
        "fade-in": {
          "0%": { opacity: "0", transform: "translateY(8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        "fade-in": "fade-in 0.2s ease-out",
      },
    },
  },
  plugins: [],
};
