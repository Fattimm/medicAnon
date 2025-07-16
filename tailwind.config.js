/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./medicanon/templates/**/*.html",
    "./medicanon/static/**/*.js",
  ],
  theme: {
    extend: {
      colors: {
        // 'medic-blue': '#1e40af',
        'medic-blue': '#1E90FF',
        'medic-blue-dark': '#1E40AF',
        'medic-lime': '#84cc16',
        'medic-gray': '#f3f4f6',
        'medic-red': '#dc2626',
      },
    },
  },
  plugins: [],
};