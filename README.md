# eLearning Blockchain Certification

**Autor:** `Pedro Pereira`

**Versión:** `18.0.1.0.0`

**Categoría:** `Website/eLearning`

**Dependencias:** `website_slides`, `website_sale_slides`, `survey`, `sale`, `odoo_blockchain_core`

---

## 📋 Descripción

Este módulo extiende el sistema de eLearning de Odoo 18 para permitir la certificación en blockchain de los certificados de cursos, como opción adicional de pago para los alumnos.

### Características Principales

- ✅ El profesor puede habilitar la certificación blockchain por curso
- ✅ Precio configurable para cada curso
- ✅ Producto opcional automático para la certificación
- ✅ Hash SHA-256 del PDF real del certificado
- ✅ Integración completa con `odoo_blockchain_core`
- ✅ Sin modificaciones de frontend necesarias

---

## 🔧 Instalación

### Requisitos Previos

1. Odoo 18 Community o Enterprise
2. Módulos base instalados:
   - `website_slides` (eLearning)
   - `website_sale_slides` (Venta de cursos)
   - `survey` (Encuestas/Certificaciones)
   - `sale` (Ventas)
3. Módulo `odoo_blockchain_core` instalado y configurado

### Pasos de Instalación

1. Copiar la carpeta `elearning_blockchain_certification` al directorio de addons
2. Actualizar la lista de módulos en Odoo
3. Instalar el módulo desde Aplicaciones

---

## 📖 Guía de Uso

### Para el Profesor/Administrador

#### 1. Configurar el Survey/Certificado

1. Ir a **Encuestas** > Seleccionar el survey de certificación
2. Activar **"Certificable en Blockchain"** (solo visible si es certificación)
3. Guardar

#### 2. Configurar el Curso

1. Ir a **eLearning** > Seleccionar el curso
2. En la pestaña **Opciones**, buscar sección **"Certificación Blockchain"**
3. Activar **"Certificación Blockchain Habilitada"**
4. Definir el **precio adicional** para la certificación
5. Seleccionar el **survey** cuyo certificado se registrará en blockchain
6. Guardar

> El sistema creará automáticamente un producto de certificación y lo vinculará como producto opcional del curso.

### Para el Alumno

1. Navegar al curso en el sitio web
2. Hacer clic en **"Comprar"** o **"Inscribirse"**
3. Si el curso tiene certificación blockchain, aparecerá la opción de añadirla
4. Completar la compra
5. Realizar el curso y aprobar el examen
6. Si compró la certificación, el certificado se registrará automáticamente en blockchain

---

## 🔄 Flujo Técnico

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        CONFIGURACIÓN (Profesor)                        │
├─────────────────────────────────────────────────────────────────────────┤
│  1. Marcar survey como "Certificable en Blockchain"                    │
│  2. Activar certificación en el curso                                  │
│  3. Definir precio → Sistema crea producto automático                  │
│  4. Producto se vincula como opcional del curso                        │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           COMPRA (Alumno)                              │
├─────────────────────────────────────────────────────────────────────────┤
│  1. Alumno añade curso al carrito                                      │
│  2. Odoo sugiere producto de certificación (nativo)                    │
│  3. Al confirmar pedido:                                               │
│     - Se crea inscripción (slide.channel.partner)                      │
│     - Si compró certificación → has_blockchain_certification = True    │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     CERTIFICACIÓN (Automático)                          │
├─────────────────────────────────────────────────────────────────────────┤
│  1. Alumno completa el survey de certificación                         │
│  2. Sistema verifica 3 condiciones:                                    │
│     ✓ survey.blockchain_certifiable == True                            │
│     ✓ channel.blockchain_certification_enabled == True                 │
│     ✓ enrollment.has_blockchain_certification == True                  │
│  3. Si todas OK → Generar PDF → Calcular SHA-256 → Registrar en BC     │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 🔐 Las 3 Condiciones

Para que un certificado se registre en blockchain, deben cumplirse **exactamente** estas 3 condiciones:

| #   | Condición                                              | Campo                              | Modelo                  |
| --- | ------------------------------------------------------ | ---------------------------------- | ----------------------- |
| 1   | El survey está marcado como certificable en blockchain | `blockchain_certifiable`           | `survey.survey`         |
| 2   | El curso tiene la certificación habilitada             | `blockchain_certification_enabled` | `slide.channel`         |
| 3   | El alumno compró la certificación para ESE curso       | `has_blockchain_certification`     | `slide.channel.partner` |

> **Importante**: La condición 3 es específica por curso. Un alumno puede tener certificación blockchain para el Curso A pero no para el Curso B.

---

## 📁 Estructura del Módulo

```
elearning_blockchain_certification/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   ├── product_product.py      # Campo certification_for_channel_id
│   ├── slide_channel.py        # Configuración de certificación por curso
│   ├── slide_channel_partner.py # Tracking de compras por alumno
│   ├── survey_survey.py        # Campo blockchain_certifiable
│   ├── survey_user_input.py    # Lógica de verificación y registro
│   └── sale_order.py           # Activación automática al comprar
├── views/
│   ├── slide_channel_views.xml # UI para cursos
│   └── survey_survey_views.xml # UI para surveys
├── security/
│   └── ir.model.access.csv     # Permisos de acceso
└── README.md
```

---

## ⚠️ Notas Importantes

1. **El curso debe tener un producto asociado** (política de inscripción "Por pago") antes de activar la certificación blockchain.

2. **El producto de certificación no se borra** al desactivar la certificación, solo se desactiva, para mantener trazabilidad.

3. **El hash se calcula del PDF real** del certificado generado. Si el PDF no puede generarse, se usa un fallback con los datos críticos.

4. **La certificación se activa en el momento de la compra**, no se puede añadir después (por diseño, para evitar manipulación).
