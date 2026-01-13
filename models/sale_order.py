# -*- coding: utf-8 -*-
"""
Extensión de sale.order para solucionar el problema de acceso a cursos.
"""
from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _action_confirm(self):
        """
        Override para garantizar acceso al curso y configurar derechos de certificación.
        """
        _logger.info(">>> ELEARNING BLOCKCHAIN: Ejecutando _action_confirm <<<")
        
        # 1. Ejecutar lógica estándar 
        result = super(SaleOrder, self)._action_confirm()

        # 2. Lógica adicional: Buscar cursos por Template
        so_lines = self.env['sale.order.line'].search([('order_id', 'in', self.ids)])
        products = so_lines.mapped('product_id')
        purchased_templates = products.mapped('product_tmpl_id')

        # Buscar canales pagados vinculados a los templates comprados
        channels = self.env['slide.channel'].sudo().search([
            ('enroll', '=', 'payment'),
            ('product_id.product_tmpl_id', 'in', purchased_templates.ids)
        ])
        
        if not channels:
            return result

        channels_per_so = {sale_order: self.env['slide.channel'] for sale_order in self}
        
        for so_line in so_lines:
            product_tmpl = so_line.product_id.product_tmpl_id
            matching_channels = channels.filtered(
                lambda c: c.product_id.product_tmpl_id == product_tmpl
            )
            
            if matching_channels:
                channels_per_so[so_line.order_id] |= matching_channels
                
                # --- NUEVA LÓGICA DE DERECHOS ---
                # Verificar si compró la variante blockchain
                # Usamos el nombre del valor del atributo para detectar si es "Certificado Blockchain"
                is_blockchain_variant = False
                for ptav in so_line.product_id.product_template_attribute_value_ids:
                    if ptav.attribute_id.name == 'Certificación Blockchain' and ptav.name == 'Certificado Blockchain':
                        is_blockchain_variant = True
                        break
                
                # Actualizar derechos en la inscripción
                for channel in matching_channels:
                    # Asegurar que el usuario está inscrito (si no lo hizo el super)
                    channel.sudo()._action_add_members(so_line.order_id.partner_id)
                    
                    enrollment = self.env['slide.channel.partner'].sudo().search([
                        ('channel_id', '=', channel.id),
                        ('partner_id', '=', so_line.order_id.partner_id.id)
                    ], limit=1)
                    
                    if enrollment:
                        # SETEAMOS explícitamente True o False.
                        # Esto corrige re-inscripciones: Si paga estándar, pierde derechos antiguos.
                        enrollment.write({'blockchain_certification_rights': is_blockchain_variant})
                        _logger.info("Derechos Blockchain para %s en curso %s: %s", 
                                     so_line.order_id.partner_id.name, channel.name, is_blockchain_variant)

        return result
