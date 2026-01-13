# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request, content_disposition
from odoo.addons.survey.controllers.main import Survey
import base64
import logging

_logger = logging.getLogger(__name__)

class SurveyBlockchain(Survey):
    
    @http.route(['/survey/<int:survey_id>/get_certification'], type='http', auth='user', methods=['GET'], website=True)
    def survey_get_certification(self, survey_id, **kwargs):
        """
        Sobrescribe la ruta de descarga para servir SIEMPRE la versión inmutable
        guardada en blockchain (si existe), garantizando que el hash coincida.
        """
        _logger.info("Interceptando descarga de certificado para Survey ID: %s", survey_id)
        
        # Copia de la lógica original para encontrar el intento exitoso
        survey = request.env['survey.survey'].sudo().search([
            ('id', '=', survey_id),
            ('certification', '=', True)
        ])

        if not survey:
            return request.redirect("/")

        # Buscar intento exitoso del usuario actual
        succeeded_attempt = request.env['survey.user_input'].sudo().search([
            ('partner_id', '=', request.env.user.partner_id.id),
            ('survey_id', '=', survey_id),
            ('scoring_success', '=', True)
        ], limit=1)

        if not succeeded_attempt:
            # Fallback a lógica original que levantará UserError si no hay éxito
            return super(SurveyBlockchain, self).survey_get_certification(survey_id, **kwargs)

        # Verificar si hay una versión inmutable blockchain vinculada (búsqueda por adjunto)
        if hasattr(succeeded_attempt, '_get_immutable_certificate_attachment'):
            attachment = succeeded_attempt._get_immutable_certificate_attachment()
            
            if attachment:
                _logger.info("✅ SIRVIENDO CERTIFICADO INMUTABLE (Adjunto ID: %s)", attachment.id)
                pdf_content = base64.b64decode(attachment.datas)
                report_content_disposition = content_disposition(attachment.name or 'Certification.pdf')
                
                return request.make_response(pdf_content, headers=[
                    ('Content-Type', 'application/pdf'),
                    ('Content-Length', len(pdf_content)),
                    ('Content-Disposition', report_content_disposition),
                ])
            else:
                 _logger.info("⚠️ No se encontró adjunto inmutable para intento exitoso %s", succeeded_attempt.id)
        
        _logger.info("⚡ Generando certificado dinámico")
        return super(SurveyBlockchain, self).survey_get_certification(survey_id, **kwargs)
