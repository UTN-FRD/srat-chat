# Sistema de Chatbot Académico con Agentes Especializados

Sistema de chatbot inteligente desarrollado para manejar consultas académicas y del sistema SRAT mediante múltiples agentes especializados que procesan automáticamente diferentes tipos de solicitudes.

## Características Principales

- **Arquitectura Multi-Agente**: Sistema distribuido con tres agentes especializados que clasifican y procesan consultas automáticamente
- **Integración Gmail**: Sistema de notificaciones automáticas por correo electrónico para información sensible
- **Acceso a Base de Datos**: Conexión directa con MySQL para consultas académicas en tiempo real
- **Interfaz Web**: Aplicación Flask con interfaz de usuario moderna y responsiva
- **Gestión de Contexto**: Mantenimiento del historial de conversación durante toda la sesión

## Arquitectura del Sistema

### Agente SRAT
**Propósito**: Gestión de consultas relacionadas con el sistema de carga de temas académicos

**Funcionalidades**:
- Resolución de problemas de autenticación y acceso
- Asistencia con credenciales de usuario (legajo y contraseña)
- Consultas sobre horarios y asignaturas del sistema
- Generación automática de notificaciones por correo electrónico

### Agente DATABASE
**Propósito**: Procesamiento de consultas académicas sobre información de usuarios

**Funcionalidades**:
- Consulta de materias asignadas por número de legajo
- Obtención de información de carreras académicas
- Acceso a datos personales académicos
- Envío seguro de información sensible mediante correo electrónico

### Agente GENERAL
**Propósito**: Gestión de interacciones iniciales y orientación de usuarios

**Funcionalidades**:
- Procesamiento de saludos y bienvenidas
- Orientación sobre servicios disponibles en el sistema
- Respuestas a consultas generales no especializadas

## Requisitos del Sistema

- Python 3.8 o superior
- Servidor MySQL en funcionamiento
- Cuenta de Google con Gmail API configurada
- Cuenta de Groq para acceso al modelo de lenguaje

## Instalación y Configuración

### Preparación del Entorno

1. **Navegación al directorio del proyecto**
   ```bash
   cd c:\python\Chatbot
   ```

2. **Creación del entorno virtual**
   ```bash
   python -m venv .venv
   ```

3. **Activación del entorno virtual**
   ```bash
   # Windows
   .\.venv\Scripts\activate
   
   # Linux/Mac
   source .venv/bin/activate
   ```

4. **Instalación de dependencias**
   ```bash
   pip install -r requirements.txt
   ```

### Configuración de Variables de Entorno

Crear archivo `.env` en el directorio raíz con la siguiente estructura:
```env
GROQ_API_KEY=tu_api_key_de_groq
SECRET_KEY=tu_clave_secreta_flask
SQLALCHEMY_DATABASE_URI=mysql://usuario:password@localhost:3306/nombre_bd
```

### Configuración de Gmail API

1. Crear proyecto en [Google Cloud Console](https://console.cloud.google.com/)
2. Habilitar Gmail API en el proyecto
3. Generar credenciales OAuth 2.0
4. Descargar archivo `credentials.json` y ubicarlo en el directorio del proyecto
5. Ejecutar la aplicación una vez para generar automáticamente el archivo `token.json`

## Ejecución del Sistema

### Método 1: Línea de Comandos
```bash
cd c:\python\Chatbot
.\.venv\Scripts\activate
python main.py
```

### Método 2: Entorno de Desarrollo Integrado
Ejecutar directamente `main.py` desde cualquier IDE compatible (VS Code, PyCharm, etc.)

## Guía de Uso

1. Acceder a la aplicación mediante navegador web en `http://localhost:5000`
2. Introducir consulta en el campo de texto del chat
3. El sistema clasificará automáticamente el tipo de consulta
4. El agente especializado correspondiente procesará y responderá la solicitud

### Ejemplos de Consultas por Categoría

**Consultas SRAT:**
- "No puedo ingresar al sistema"
- "¿Cómo cargo temas?"
- "Olvidé mi contraseña"

**Consultas DATABASE:**
- "¿Qué materias doy con legajo 50443?"
- "¿A qué carrera pertenezco?"
- "Mi legajo es 12345, ¿qué materias tengo?"

**Consultas GENERAL:**
- "Hola"
- "¿Qué servicios ofrecen?"
- "Buenos días"

## Configuración de Base de Datos

El sistema requiere una base de datos MySQL con las siguientes tablas principales:
- `usuarios` (legajo, email, información personal)
- `cargos` (relación usuario-asignatura)
- `asignaturas` (materias y carreras)
- `asignaturas_materias` (nombres de materias)
- `asignaturas_carreras` (nombres de carreras)

## Configuración de Gmail

### Archivos Requeridos
- `credentials.json`: Credenciales OAuth 2.0 de Google
- `token.json`: Token de acceso (generado automáticamente)

### Permisos Necesarios
- `https://mail.google.com/` (lectura y envío de correos electrónicos)

## Consideraciones de Seguridad

- **Manejo de Información Sensible**: Los datos personales se transmiten exclusivamente por correo electrónico, nunca se muestran en la interfaz de chat
- **Autenticación**: Requiere credenciales válidas de Google para funcionamiento completo
- **Conexión de Base de Datos**: Utiliza conexión segura con MySQL
- **Gestión de Credenciales**: Las claves sensibles se almacenan en variables de entorno

## Estructura del Proyecto

```
Chatbot/
├── main.py                 # Aplicación principal Flask
├── requirements.txt        # Dependencias Python
├── credentials.json       # Credenciales Gmail API
├── token.json             # Token de acceso Gmail
├── .env                   # Variables de entorno
├── templates/
│   └── index.html         # Interfaz web
└── README.md             # Documentación del proyecto
```

## Solución de Problemas Comunes

### Error: "No such file or directory: 'credentials.json'"
**Solución**: Verificar que el archivo `credentials.json` esté ubicado en el directorio del proyecto. El sistema utiliza rutas absolutas para garantizar funcionamiento desde cualquier ubicación.

### Error: "ModuleNotFoundError"
**Solución**: 
- Activar el entorno virtual: `.\.venv\Scripts\activate`
- Instalar dependencias: `pip install -r requirements.txt`

### Error de Conexión a Base de Datos
**Solución**:
- Verificar que el servidor MySQL esté ejecutándose
- Comprobar la cadena de conexión en el archivo `.env`
- Validar credenciales de acceso a la base de datos

### Error de Gmail API
**Solución**:
- Verificar validez del archivo `credentials.json`
- Confirmar que Gmail API esté habilitada en Google Cloud Console
- Regenerar `token.json` eliminando el archivo existente y ejecutando la aplicación nuevamente

