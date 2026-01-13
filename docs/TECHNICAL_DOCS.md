# Documentación Técnica: eLearning Blockchain Certification

**Fecha de Generación:** 12 de Enero, 2026
**Autor:** Pedro Pereira (Generado por Asistente AI)

---

## Índice

1. [Descripción General](#1-descripción-general)
2. [Manifiesto del Módulo (`__manifest__.py`)](#2-manifiesto-del-módulo-__manifest__py)
3. [Seguridad (`security/ir.model.access.csv`)](#3-seguridad-securityirmodelaccesscsv)
4. [Modelos (`models/`)](#4-modelos-models)
   - [Sale Order (`sale_order.py`)](#41-sale-order-modelssale_orderpy)
   - [Slide Channel (`slide_channel.py`)](#42-slide-channel-modelsslide_channelpy)
   - [Slide Slide (`slide_slide.py`)](#43-slide-slide-modelsslide_slidepy)
   - [Survey User Input (`survey_user_input.py`)](#44-survey-user-input-modelssurvey_user_inputpy)
5. [Controladores (`controllers/main.py`)](#5-controladores-controllersmainpy)
6. [Vistas y Templates (`views/`)](#6-vistas-y-templates-views)

---

## 1. Descripción General

Este módulo extiende la funcionalidad nativa de eLearning y Certificaciones de Odoo para integrar el registro de certificados en Blockchain. Permite vender cursos con una variante opcional ("Con Certificación Blockchain") que tiene un sobrecoste. Al aprobar el curso (survey), el sistema genera un certificado inmutable (PDF), calcula su hash y lo registra en la blockchain utilizando el núcleo `odoo_blockchain_core`.

---

## 2. Manifiesto del Módulo (`__manifest__.py`)

Define los metadatos y dependencias del módulo.

- **Dependencias Clave:**
  - `website_slides`: Núcleo de eLearning.
  - `website_slides_survey`: Puente entre slides y certificaciones.
  - `website_sale`: eCommerce para variantes de productos.
  - `website_sale_slides`: Venta de cursos.
  - `odoo_blockchain_core`: Módulo conector para la blockchain (Smart Contracts, RPC).
- **Archivos de Datos:** Carga vistas XML y reglas de acceso CSV.

---

## 3. Seguridad (`security/ir.model.access.csv`)

Define los permisos de acceso (ACLs) para los modelos.

| ID                                    | Nombre                              | Modelo              | Grupo                                 | Lectura | Escritura | Creación | Eliminación |
| ------------------------------------- | ----------------------------------- | ------------------- | ------------------------------------- | ------- | --------- | -------- | ----------- |
| `access_slide_channel_blockchain`     | slide.channel blockchain access     | `slide.channel`     | `base.group_user` (Usuarios internos) | ✅      | ❌        | ❌       | ❌          |
| `access_slide_slide_blockchain`       | slide.slide blockchain access       | `slide.slide`       | `base.group_user`                     | ✅      | ❌        | ❌       | ❌          |
| `access_survey_user_input_blockchain` | survey.user_input blockchain access | `survey.user_input` | `base.group_user`                     | ✅      | ❌        | ❌       | ❌          |

> **Nota:** Se otorgan permisos básicos de lectura a usuarios internos para asegurar que puedan ver las nuevas propiedades blockchain en los modelos extendidos.

---

## 4. Modelos (`models/`)

### 4.1. Sale Order (`models/sale_order.py`)

**Extiende:** `sale.order`
**Propósito:** Asegurar que el usuario reciba acceso al curso cuando compra una **variante** del producto asociado (ej. la variante "Con Certificación"), ya que Odoo nativo a veces falla si la variante no coincide exactamente con la definida en el canal.

#### Métodos:

- **`_action_confirm(self)`**
  - **Tipo:** Override (super).
  - **Funcionalidad:**
    1. Ejecuta la confirmación estándar de la orden.
    2. Itera sobre las líneas del pedido (`sale.order.line`).
    3. Obtiene los **Templates** de producto comprados.
    4. Busca canales de eLearning (`slide.channel`) de tipo pago (`enroll='payment'`) enlazados a esos templates.
    5. Si encuentra coincidencia (mismo template, aunque sea otra variante), fuerza la inscripción usando `_action_add_members`.
  - **Justificación:** Resuelve el bug/limitación donde comprar la variante "Certificada" no inscribía al usuario en el curso.

---

### 4.2. Slide Channel (`models/slide_channel.py`)

**Extiende:** `slide.channel`
**Propósito:** Configurar si un curso ofrece certificación blockchain y gestionar automáticamente las variantes de producto (Precio extra).

#### Campos:

- `blockchain_certification_enabled` (`Boolean`): Toggle para habilitar la funcionalidad en el curso.
- `blockchain_certification_price` (`Float`): Precio adicional que se cobrará por la certificación.

#### Métodos:

- **`_get_blockchain_attribute(self)`**
  - **Retorna:** `(Attribute, Value_Standard, Value_Certified)`
  - **Lógica:** Busca (o crea si no existe) el Atributo de Producto "Certificación Blockchain" y sus valores "Estándar" y "Certificado Blockchain".
- **`_update_product_variants(self)`**
  - **Lógica:**
    1. Obtiene el producto vinculado al curso.
    2. Si `blockchain_certification_enabled` es `True`: Añade la línea de atributo al producto para generar las dos variantes. Configura el `price_extra` en la variante certificada. Re-asigna el `product_id` del canal a la variante estándar para mantener consistencia.
    3. Si es `False`: Pone el precio extra a 0.
- **`write(self, vals)` / `create(self, vals_list)`**
  - **Hooks:** Llaman a `_update_product_variants` cuando se modifican los campos de configuración blockchain.

---

### 4.3. Slide Slide (`models/slide_slide.py`)

**Extiende:** `slide.slide`
**Propósito:** Permitir marcar qué contenido específico (de tipo certificación) desencadenará el registro en blockchain.

#### Campos:

- `blockchain_certifiable` (`Boolean`): "Registrar en Blockchain". Solo visible si la categoría es certificación.

#### Métodos:

- **`_onchange_slide_category_blockchain(self)`**
  - **Lógica:** Si la categoría del slide cambia a algo que no sea 'certification', fuerza `blockchain_certifiable = False`.

---

### 4.4. Survey User Input (`models/survey_user_input.py`)

**Extiende:** `survey.user_input`, `blockchain.certified.mixin`
**Propósito:** Núcleo de la lógica de certificación. Maneja la generación del PDF inmutable, el hashing y la comunicación con el usuario y la blockchain.

#### Campos:

- `blockchain_certificate_hash` (`Char`): Almacena el hash SHA-256 del PDF generado.

#### Métodos Clave:

- **`_get_immutable_certificate_attachment(self)`**
  - Busca el adjunto técnico específico marcado como "Certificado Blockchain Inmutable".
- **`_generate_and_store_certificate(self)`**
  - **Crítico:** Genera el PDF del reporte usando `ir.actions.report`.
  - **Limpieza:** Borra el adjunto temporal ("side-effect") que Odoo genera automáticamente al renderizar reportes, para evitar duplicados.
  - **Persistencia:** Crea un nuevo adjunto inmutable (`ir.attachment`).
  - **Hashing:** Calcula SHA-256 del contenido binario y lo guarda en `blockchain_certificate_hash`.
- **`_compute_blockchain_hash(self)`**
  - Implementación del hook del Mixin. Devuelve el hash almacenado o intenta generarlo si falta.
- **`_should_certify_on_blockchain(self)`**
  - **Lógica de Negocio:** Determina si este intento debe ir a blockchain.
  - **Condiciones:** El usuario aprobó + El slide es `blockchain_certifiable` + El usuario COMPRÓ la variante "Certificado Blockchain".
- **`_mark_done(self)`**
  - **Override Maestro:** Intercepta el momento en que se finaliza el examen.
  - **Flujo Especial Blockchain:**
    1. Llama a `super()` para lógica estándar (scoring).
    2. Si aplica blockchain:
       - Genera PDF Inmutable.
       - Llama a `action_blockchain_register()` (del Core).
       - **Email Custom:** Envía el correo de felicitación manualmente usando `message_post` y adjuntando **solo** el PDF inmutable. Esto evita que Odoo genere un nuevo PDF dinámico al enviar el template por defecto.

---

## 5. Controladores (`controllers/main.py`)

### Clase `SurveyBlockchain`

**Extiende:** `odoo.addons.survey.controllers.main.Survey`

#### Rutas:

- **`/survey/<int:survey_id>/get_certification`** (Override)
  - **Propósito:** Controlar qué archivo descarga el usuario desde el navegador.
  - **Lógica:**
    1. Verifica si el usuario tiene un intento aprobado.
    2. Busca si ese intento tiene un **certificado inmutable** generado (`_get_immutable_certificate_attachment`).
    3. Si existe: Sirve ese archivo binario exacto (asegurando validez del hash).
    4. Si no existe: Fallback a la generación dinámica estándar de Odoo.

---

## 6. Vistas y Templates (`views/`)

### 6.1. `views/slide_channel_views.xml`

- **ID:** `view_slide_channel_form_blockchain`
- **Hereda de:** `website_slides.view_slide_channel_form`
- **Modificación:** Añade una pestaña o grupo en el formulario del curso para configurar:
  - Toggle `blockchain_certification_enabled`.
  - Campo monetario `blockchain_certification_price`.

### 6.2. `views/slide_slide_views.xml`

- **ID:** `view_slide_slide_form_blockchain` & `view_slide_channel_form_blockchain_column`
- **Modificación:**
  - En formulario de slide: Añade toggle `blockchain_certifiable` si es tipo certificación.
  - En lista de slides del canal: Añade columna para ver rápidamente cuales son certificables.

### 6.3. `views/website_sale_slides_overrides.xml`

- **Template:** `blockchain_course_purchased_confirmation_override`
- **Hereda de:** `website_sale_slides.course_purchased_confirmation_message`
- **Problema Solucionado:** La vista original busca cursos iterando `line.product_id.channel_ids`. Si compramos una variante que no es la principal del canal, la lista sale vacía.
- **Solución:** Cambia la iteración para buscar en `line.product_id.product_tmpl_id.product_variant_ids.mapped('channel_ids')`. Esto encuentra el canal sin importar qué variante del producto se compró.
