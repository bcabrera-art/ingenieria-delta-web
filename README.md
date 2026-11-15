# Ingeniería Delta — Sitio Web

Repositorio de control de versiones para el sitio web corporativo de **Ingeniería Delta** (previo al despliegue en producción en `www.ingenieriadelta.cl`).

## Estructura del proyecto

- `index.html` — Página principal del sitio web.
- `enviar.php` — Script de envío de solicitudes de cotización (compatible con cPanel / PHP estándar).
- `assets/css/styles.css` — Hoja de estilos principal.
- `assets/js/app.js` — Lógica e interactividad del frontend.
- `assets/img/` — Imágenes del sitio web.
- `assets/video/hero_patagonia.mp4` — Video principal de la sección hero.

## Flujo de trabajo

1. Desarrollar e iterar localmente sobre la rama `main` (o ramas de funcionalidades).
2. Registrar los cambios con Git (`git add`, `git commit`, `git push`).
3. Una vez validadas las iteraciones, desplegar en `www.ingenieriadelta.cl`.
