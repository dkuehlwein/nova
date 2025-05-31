const basePath = import.meta.env.VITE_API_URL
	? import.meta.env.VITE_API_URL
	: import.meta.env.DEV
	? `http://localhost:${import.meta.env.VITE_API_PORT}/`
	: window.location.href;
export const api = `${basePath.at(-1) === "/" ? basePath : `${basePath}/`}api`;
