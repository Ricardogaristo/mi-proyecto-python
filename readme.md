📌 Aplicación Web de Gestión de Tareas

Aplicación web desarrollada en Python utilizando Flask para la gestión y organización de tareas mediante categorías y fechas.

El sistema permite administrar tareas desde una interfaz web, con soporte para base de datos SQLite y posibilidad de publicación temporal en internet mediante Cloudflare Tunnel.

🚀 Funcionalidades

✅ Registro de nuevas tareas11

✅ Organización por categorías

✅ Visualización estructurada por fecha

✅ Panel de administración

✅ Persistencia de datos con SQLite

✅ Acceso local y publicación pública temporal

🛠 Tecnologías Utilizadas

Python 3

Flask

SQLite

HTML / CSS

Cloudflare Tunnel

📂 Estructura del Proyecto
/templates
/static
app.py
database.db


templates/ → Archivos HTML

static/ → Archivos CSS, JS e imágenes

app.py → Archivo principal de la aplicación

database.db → Base de datos SQLite

▶ Cómo Ejecutar la Aplicación
1️⃣ Crear entorno virtual
python -m venv venv

2️⃣ Activar entorno virtual (Windows)
venv\Scripts\activate

3️⃣ Instalar dependencias
pip install -r requirements.txt

4️⃣ Ejecutar la aplicación
python app.py


La aplicación estará disponible en:

http://127.0.0.1:5000

🌐 Publicación Temporal

Para exponer la aplicación públicamente:

cloudflared tunnel --url http://localhost:5000

👤 Autor

Ricardogaristo

🚀 Ahora súbelo a GitHub

Desde tu carpeta del proyecto:

git add README.md
git commit -m "Actualizo README con descripción profesional del proyecto"
git push