{
    'name': 'Odoo Blockchain Certification eLearning',
    'version': '18.0.1.0.0',
    'category': 'Website/eLearning',
    'summary': 'Certificación blockchain de cursos',
    'description': """
        Este módulo añade la posibilidad de certificar en blockchain los certificados
        de cursos para alumnos que seleccionen la variante "Con Certificación".
        
        Características:
        - Configuración automática de Variantes de Producto (Con/Sin Blockchain)
        - Precio extra configurable
        - Nativo de Odoo (usa atributos de producto existentes)
        - Validación automática al completar el curso
    """,
    'author': 'Pedro Pereira',
    'depends': [
        'website_slides',        
        'website_slides_survey', 
        'website_sale',          
        'website_sale_slides',  
        'survey',
        'sale',
        'odoo_blockchain_core'
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/slide_channel_views.xml',
        'views/slide_slide_views.xml',
        'views/website_sale_slides_overrides.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
