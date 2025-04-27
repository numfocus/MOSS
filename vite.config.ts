import path from "node:path"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"
import wasm from "vite-plugin-wasm"
import topLevelAwait from "vite-plugin-top-level-await"
import tailwind from '@tailwindcss/vite'


export default defineConfig({
	plugins: [react(), wasm(), tailwind(), topLevelAwait()],
	resolve: {
		alias: {
			"@": path.resolve(__dirname, "./src"),
			"@/components": path.resolve(__dirname, "./src/components"),
			"@/components/ui": path.resolve(__dirname, "./src/components/ui"),
			"@/lib": path.resolve(__dirname, "./src/lib"),
			"@/hooks": path.resolve(__dirname, "./src/hooks"),
		},
	},
	optimizeDeps: {
		exclude: ["@surrealdb/wasm"],
		esbuildOptions: {
			target: "esnext",
		},
	},
	esbuild: {
		supported: {
			"top-level-await": true
		},
	},
	assetsInclude: [/\.(surql)$/, /\.wasm$/],
})