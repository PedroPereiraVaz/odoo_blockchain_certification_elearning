# Odoo Blockchain Certification eLearning

**Autor:** `Pedro Pereira`
**Versión:** `18.0.1.0.0`
**Categoría:** `Website/eLearning`
**Licencia:** `LGPL-3`

---

## 📋 Descripción

Este módulo transforma el sistema de eLearning de Odoo 18 en una plataforma de certificación validada en Blockchain. Permite a las instituciones educativas ofrecer **cursos con certificación opcional en blockchain** mediante variantes de producto nativas.

Al aprobar el examen (Survey), el sistema genera un **Certificado PDF Inmutable**, calcula su hash criptográfico (SHA-256) y lo registra permanentemente en la blockchain utilizando el núcleo `odoo_blockchain_core`.

### ✅ Características Principales

1.  **Variantes de Producto Automáticas**: Al activar la certificación en un curso, se crean automáticamente las variantes "Estándar" y "Certificado Blockchain" con un sobrecoste configurable.
2.  **Certificado Inmutable**: Se genera y almacena un PDF único que no puede ser modificado posteriormente. Este archivo exacto es el que se certifica.
3.  **Validación de Compra Estricta**: El sistema verifica que el estudiante haya comprado específicamente la variante "Certificado Blockchain" antes de iniciar el proceso de registro.
4.  **Integridad Criptográfica**: El hash SHA-256 se calcula directamente del contenido binario del PDF. Si el PDF no se puede generar, el proceso se detiene para garantizar la integridad (no se usan fallbacks de datos JSON).
5.  **Entrega Segura**: El correo de felicitación envía el PDF inmutable exacto, evitando que Odoo genere una nueva versión dinámica en el momento del envío.
6.  **Corrección de Flujo eLearning**: Incluye "fixes" para asegurar que la compra de variantes de curso otorgue acceso correcto al contenido (algo que Odoo nativo no maneja bien por defecto).

---

## 🔧 Dependencias

Para su correcto funcionamiento, requiere:

- `odoo_blockchain_core` (Núcleo de conexión Blockchain)
- `website_slides` (eLearning)
- `website_slides_survey` (Certificaciones)
- `website_sale` (eCommerce)
- `survey`
- `sale`

---

## 📖 Guía de Configuración (Administrador/Profesor)

### 1. Preparar el Contenido (Survey)

1.  Vaya a **Encuestas** (Surveys).
2.  Cree o edite una Certificación.
3.  _El survey se vinculará al curso normalmente como una diapositiva (Slide)._

### 2. Configurar el Curso

1.  Vaya a **eLearning** > **Cursos**.
2.  Seleccione el curso deseado.
3.  En la pestaña **Opciones**, busque el grupo **Certificación Blockchain**.
4.  Active **"Certificación Blockchain Habilitada"**.
5.  Establezca el **Precio Extra Certificación** (ej: 50.00 €).
    - _Nota: Esto configurará automáticamente las variantes en el producto asociado._

### 3. Configurar el Slide de Certificación

1.  Dentro del curso, vaya a **Contenido** y abra la diapositiva de tipo **Certificación**.
2.  Asegúrese de que el Check **"Registrar en Blockchain"** esté activo.

---

## 🎒 Flujo del Estudiante

1.  **Compra**: El estudiante navega al curso en el sitio web. Verá dos opciones:
    - **Estándar**: Precio base.
    - **Certificado Blockchain**: Precio base + Precio extra.
2.  **Acceso**: Al comprar cualquiera de las dos, obtiene acceso inmediato al curso.
3.  **Aprobación**: El estudiante completa el contenido y aprueba el examen final.
4.  **Emisión**:
    - Si compró la variante **Estándar**: Recibe su diploma normal de Odoo.
    - Si compró la variante **Blockchain**:
      1.  Se genera el PDF inmutable.
      2.  Se registra el hash en Blockchain (Smart Contract).
      3.  Recibe un correo con el PDF inmutable adjunto.

---

## 🛠️ Detalles Técnicos para Desarrolladores

### Estructura de Hash

El hash registrado en la blockchain corresponde a:

```python
hash_hex = hashlib.sha256(pdf_content_binary).hexdigest()
```

Esto permite que cualquier tercero con el archivo PDF pueda validar su autenticidad recalculando el hash y consultando la blockchain.

### Modelos Extendidos

- `slide.channel`: Gestión de configuración y variantes.
- `slide.slide`: Flag de activación por contenido.
- `survey.user_input`: Lógica core (Generación PDF, Hashing, Registro).
- `sale.order`: Lógica de acceso por variantes (`_action_confirm`).

### Seguridad

- **Permisos de Acceso**: Configurados en `security/ir.model.access.csv` para dar lectura a usuarios base sobre los nuevos campos.
- **Prevención de Fraude**: El sistema verifica `sale.order.line` para confirmar que se pagó por la certificación específica del curso en cuestión.
