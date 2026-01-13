# -*- coding: utf-8 -*-
"""
Extensión de slide.slide para añadir campo de certificación blockchain.
"""
from odoo import models, fields, api


class SlideSlide(models.Model):
    """
    Extensión del modelo de slides (contenidos) para permitir marcar
    un certificado como registrable en blockchain.
    """
    _inherit = 'slide.slide'

    # -------------------------------------------------------------------------
    # CAMPO DE CERTIFICACIÓN BLOCKCHAIN
    # -------------------------------------------------------------------------
    
    blockchain_certifiable = fields.Boolean(
        string='Registrar en Blockchain',
        default=False,
        help='Si está activo y el alumno ha comprado la certificación blockchain, '
             'el certificado se registrará automáticamente en blockchain al aprobar.'
    )
    
    @api.onchange('slide_category')
    def _onchange_slide_category_blockchain(self):
        """
        Si el slide no es de tipo certificación, desactivar blockchain_certifiable.
        """
        if self.slide_category != 'certification':
            self.blockchain_certifiable = False
