// frontend/tailwind.config.js
module.exports = {
  content: [
    "./index.html",
    "./src/**/*.{js,jsx,ts,tsx}"
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#f6fbff",
          100: "#e6f2ff",
          500: "#1e88ff",
        }
      }
    }
  },
  plugins: [],
};
