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
        1. Curso de pago sin producto -> No activar.
        2. Sin producto -> No precio extra.
        """
        for record in self:
            # Caso 1: Curso Pago activado sin producto
            if record.enroll == 'payment' and not record.product_id and record.blockchain_certification_enabled:
                record.blockchain_certification_enabled = False
                return {
                    'warning': {
                        'title': _('Configuración Incompleta'),
                        'message': _('Para habilitar la certificación blockchain en cursos de pago, primero debe seleccionar un Producto asociado.')
                    }
                }
            
            # Caso 2: Precio extra sin producto (Imposible cobrar)
            if not record.product_id and record.blockchain_certification_price > 0:
                record.blockchain_certification_price = 0.0
                return {
                    'warning': {
                        'title': _('Precio no permitido'),
                        'message': _('No puede establecer un precio para la certificación si el curso no tiene un producto asociado. Sin un producto, no existen variantes para gestionar el cobro.')
                    }
                }

    @api.constrains('blockchain_certification_enabled', 'enroll', 'product_id', 'blockchain_certification_price')
    def _check_blockchain_config_integrity(self):
        for record in self:
            if record.enroll == 'payment' and not record.product_id and record.blockchain_certification_enabled:
                raise UserError(_('No puede habilitar la certificación blockchain en un curso de pago sin asignar un producto.'))
            if not record.product_id and record.blockchain_certification_price > 0:
                raise UserError(_('No puede establecer un precio extra de certificación sin tener un producto asociado al curso.'))
    
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

    def write(self, vals):
        res = super().write(vals)
        if 'blockchain_certification_enabled' in vals or 'blockchain_certification_price' in vals:
            for record in self:
                if record.product_id:
                    record._update_product_variants()
        return res

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            if record.blockchain_certification_enabled and record.product_id:
                record._update_product_variants()
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
