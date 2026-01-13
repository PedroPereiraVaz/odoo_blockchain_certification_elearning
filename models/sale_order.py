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
        Override para garantizar acceso al curso independientemente de la variante comprada.
        """
        _logger.info(">>> ELEARNING BLOCKCHAIN: Ejecutando _action_confirm <<<")
        
        # 1. Ejecutar lógica estándar 
        result = super(SaleOrder, self)._action_confirm()

        # 2. Lógica adicional: Buscar cursos por Template
        # Esto soluciona que Odoo solo de acceso si coincide la variante exacta
        so_lines = self.env['sale.order.line'].search([('order_id', 'in', self.ids)])
        products = so_lines.mapped('product_id')
        purchased_templates = products.mapped('product_tmpl_id')

        _logger.info("Productos comprados templates: %s", purchased_templates.ids)

        # Buscar canales pagados vinculados a los templates comprados
        channels = self.env['slide.channel'].sudo().search([
            ('enroll', '=', 'payment'),
            ('product_id.product_tmpl_id', 'in', purchased_templates.ids)
        ])
        
        _logger.info("Canales encontrados por template: %s", channels.ids)

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

        # Añadir miembros
        for sale_order, channels_to_add in channels_per_so.items():
            if channels_to_add:
                _logger.info(
                    "Otorgando acceso EXTRA a canales: %s para %s", 
                    channels_to_add.ids, sale_order.partner_id.name
                )
                channels_to_add.sudo()._action_add_members(sale_order.partner_id)

        return result
