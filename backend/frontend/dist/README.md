# frontend/dist — archivos generados (NO editar a mano)

- `app.bundle.min.js`: los 9 scripts de `../js/` concatenados en el mismo
  orden que los cargaba `index.html` y minificados.
- `styles.min.css`: `../css/styles.css` (con sus 4 módulos) en 1 archivo
  minificado.

## Cómo regenerar tras editar `js/` o `css/`

Versión fijada: **esbuild 0.28.2** (siempre la misma, para que el bundle
salga byte-idéntico desde cualquier máquina). Con `npx`, sin instalar
nada en el repo:

```bash
cd backend/frontend
python - <<'EOF'
from pathlib import Path
order = ['escape.js','api.js','i18n.js','auth.js','predictions.js',
         'stats.js','main.js','admin.js','pwa-install.js']
Path('_bundle_src.js').write_text(
    '\n'.join((Path('js')/f).read_text(encoding='utf-8') for f in order),
    encoding='utf-8')
EOF
npx -y esbuild@0.28.2 _bundle_src.js --minify --outfile=dist/app.bundle.min.js
npx -y esbuild@0.28.2 css/styles.css --bundle --minify --outfile=dist/styles.min.css
rm _bundle_src.js
node --check dist/app.bundle.min.js
```

Luego sube el `?v=` en `index.html` (`dist/...` y `I18N_VERSION` si cambió
el diccionario) y verifica la página.
