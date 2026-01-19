# -*- coding: utf-8 -*-
"""
Extensión de slide.channel para gestionar Variantes de Producto Blockchain.
"""
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class SlideChannel(models.Model):
    _inherit = 'slide.channel'

    # -------------------------------------------------------------------------
    # CONFIGURACIÓN
    # -------------------------------------------------------------------------
    
    blockchain_certification_enabled = fields.Boolean(
        string='Certificación Blockchain Habilitada',
        default=False,
        help='Activa una variante en el producto del curso para incluir certificación blockchain.'
    )
    
    blockchain_certification_price = fields.Float(
        string='Precio Extra Certificación',
        default=0.0,
    )
    
    @api.onchange('blockchain_certification_enabled', 'enroll', 'product_id', 'blockchain_certification_price')
    def _onchange_blockchain_config_validation(self):
        """
        Valida configuración de blockchain.
        Mantenemos advertencias mínimas, pero la automatización ahora se encarga de crear el producto si falta.
        """
        for record in self:
            # Si se habilita con precio pero no hay producto, avisamos que se creará uno
            if record.blockchain_certification_enabled and not record.product_id:
                 _logger.info("Se creará un producto automáticamente para la certificación blockchain de '%s'", record.name)

    # Eliminamos las restricciones estrictas que impedían habilitar blockchain sin producto previo,
    # ya que ahora el sistema lo creará automáticamente si es necesario.
    
    # -------------------------------------------------------------------------
    # GESTIÓN DE VARIANTES
    # -------------------------------------------------------------------------
    
    def _get_blockchain_attribute(self):
        """Busca o crea el atributo y sus valores."""
        Attribute = self.env['product.attribute']
        AttributeValue = self.env['product.attribute.value']
        
        # 1. Buscar/Crear Atributo
        attr = Attribute.search([('name', '=', 'Certificación Blockchain')], limit=1)
        if not attr:
            attr = Attribute.create({
                'name': 'Certificación Blockchain',
                'create_variant': 'always', # Crear variantes inmediatamente
                'display_type': 'radio',
            })
            
        # 2. Buscar/Crear Valores
        
        # Valor estandar
        val_std = AttributeValue.search([('attribute_id', '=', attr.id), ('name', '=', 'Estándar')], limit=1)
        if not val_std:
            val_std = AttributeValue.create({'attribute_id': attr.id, 'name': 'Estándar', 'sequence': 1})
            
        # Valor certificado
        val_cert = AttributeValue.search([('attribute_id', '=', attr.id), ('name', '=', 'Certificado Blockchain')], limit=1)
        if not val_cert:
            val_cert = AttributeValue.create({'attribute_id': attr.id, 'name': 'Certificado Blockchain', 'sequence': 2})
            
        return attr, val_std, val_cert

    def _update_product_variants(self):
        """Configura el producto del curso con los atributos."""
        self.ensure_one()
        if not self.product_id:
            return

        tmpl = self.product_id.product_tmpl_id
        attr, val_std, val_cert = self._get_blockchain_attribute()
        
        # Verificar si ya tiene la línea de atributo
        line = tmpl.attribute_line_ids.filtered(lambda l: l.attribute_id == attr)
        
        if self.blockchain_certification_enabled:
            # SI está habilitado: Asegurar que existe línea con ambos valores
            if not line:
                tmpl.write({
                    'attribute_line_ids': [(0, 0, {
                        'attribute_id': attr.id,
                        'value_ids': [(6, 0, [val_std.id, val_cert.id])]
                    })]
                })
            else:
                # Actualizar valores si faltan (asegurar ambos)
                current_val_ids = line.value_ids.ids
                to_add = []
                if val_std.id not in current_val_ids:
                    to_add.append(val_std.id)
                if val_cert.id not in current_val_ids:
                    to_add.append(val_cert.id)
                
                if to_add:
                    line.write({'value_ids': [(4, vid) for vid in to_add]})
            
            # CONFIGURAR PRECIO EXTRA
            ptav = tmpl.valid_product_template_attribute_line_ids.product_template_value_ids.filtered(
                lambda v: v.product_attribute_value_id == val_cert
            )
            if ptav:
                ptav.write({'price_extra': self.blockchain_certification_price})
            
            # --- CORRECCIÓN DE DISPONIBILIDAD ---
            # Al crear variantes, el product_id original del channel puede quedar obsoleto o archivado.
            # Debemos re-apuntar el channel.product_id a la variante "Estándar".
            variant_std = tmpl.product_variant_ids.filtered(
                lambda p: val_std in p.product_template_attribute_value_ids.product_attribute_value_id
            )
            if variant_std:
                # Usamos la primera coincidencia (debería ser única por combinación de atributos)
                self.product_id = variant_std[0].id

        else:
            # NO habilitado: Poner precio extra a 0
            if line:
                 ptav = tmpl.valid_product_template_attribute_line_ids.product_template_value_ids.filtered(
                    lambda v: v.product_attribute_value_id == val_cert
                )
                 if ptav:
                     ptav.write({'price_extra': 0.0})

    def _sync_course_product(self):
        """ 
        Extiende la lógica de sincronización para manejar variantes blockchain.
        Asegura que se cree un producto incluso si el curso es gratuito pero tiene certificación de pago.
        """
        super()._sync_course_product()
        
        Product = self.env['product.product']
        for channel in self:
            # Caso Especial: Curso gratuito/público pero con certificación blockchain de pago.
            # elearning_academy solo crea producto si enroll == 'payment'.
            # Aquí forzamos la creación si hay precio de certificación.
            if not channel.product_id and channel.blockchain_certification_enabled and channel.blockchain_certification_price > 0:
                product_vals = {
                    'name': channel.name,
                    'list_price': 0.0, # El curso base es gratis
                    'type': 'service',
                    'service_tracking': 'course',
                    'invoice_policy': 'order',
                    'is_published': True,
                }
                category = self.env.ref('product.product_category_all', raise_if_not_found=False)
                if category:
                    product_vals['categ_id'] = category.id
                
                product = Product.create(product_vals)
                channel.product_id = product.id

            # Si ya tenemos producto (creado por academy o por nosotros), gestionamos las variantes
            if channel.product_id:
                channel._update_product_variants()

    def write(self, vals):
        res = super().write(vals)
        # Sincronizar si cambian campos relevantes de blockchain
        if any(f in vals for f in ['blockchain_certification_enabled', 'blockchain_certification_price']):
            self._sync_course_product()
        return res

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        # Sincronización automática al crear
        for record in records:
            if record.blockchain_certification_enabled:
                record._sync_course_product()
        return records

    def _action_add_members(self, target_partners):
        """
        Override para gestionar derechos de blockchain en inscripciones gratuitas/automáticas.
        """
        res = super(SlideChannel, self)._action_add_members(target_partners)
        
        # Lógica para Cursos/Certificados Gratuitos
        # Si la certificación está habilitada y el precio extra es 0, todos los inscritos
        # reciben el derecho automáticamente (ej: cursos públicos o gratuitos).
        for channel in self:
            if channel.blockchain_certification_enabled and channel.blockchain_certification_price == 0:
                # Buscar los enrollments recién creados/actualizados para estos partners
                enrollments = self.env['slide.channel.partner'].sudo().search([
                    ('channel_id', '=', channel.id),
                    ('partner_id', 'in', target_partners.ids)
                ])
                enrollments.write({'blockchain_certification_rights': True})
                
        return res
