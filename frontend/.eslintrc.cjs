// frontend\.eslintrc.cjs
module.exports = {
    root: true,
    env: { browser: true, es2020: true },
    extends: [
      'eslint:recommended',
      'plugin:@typescript-eslint/recommended',
      'plugin:react-hooks/recommended',
      'plugin:prettier/recommended', // Add prettier integration
    ],
    ignorePatterns: ['dist', '.eslintrc.cjs'],
    parser: '@typescript-eslint/parser',
    plugins: ['react-refresh', 'prettier'], // Ensure prettier plugin is listed
    rules: {
      'react-refresh/only-export-components': [
        'warn',
        { allowConstantExport: true },
      ],
      'prettier/prettier': 'warn', // Show prettier errors as warnings
       '@typescript-eslint/no-unused-vars': 'warn', // Warn about unused vars
       'no-unused-vars': 'off', // Disable base rule as TS rule handles it
    },
  };