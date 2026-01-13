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
