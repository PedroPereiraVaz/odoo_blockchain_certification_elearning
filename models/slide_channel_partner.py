# -*- coding: utf-8 -*-
from odoo import models, fields

class SlideChannelPartner(models.Model):
    _inherit = 'slide.channel.partner'

    blockchain_certification_rights = fields.Boolean(
        string='Derechos de Certificación Blockchain',
        default=False,
        help="Indica si este alumno tiene derecho a recibir un certificado blockchain en este curso."
    )
