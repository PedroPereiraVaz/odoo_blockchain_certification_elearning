# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
import hashlib
import logging
import json
import base64

_logger = logging.getLogger(__name__)

class SurveyUserInput(models.Model):
    _inherit = ['survey.user_input', 'blockchain.certified.mixin']
    _name = 'survey.user_input'

    blockchain_certificate_hash = fields.Char(string='Hash del Certificado', readonly=True)

    def _get_immutable_certificate_attachment(self):
        """Busca si existe un adjunto inmutable para este registro."""
        return self.env['ir.attachment'].sudo().search([
            ('res_model', '=', 'survey.user_input'),
            ('res_id', '=', self.id),
            ('description', '=', 'Certificado Blockchain Inmutable')
        ], limit=1)

    def _generate_and_store_certificate(self):
        """
        Genera el PDF, lo guarda como adjunto inmutable y calcula su hash.
        Debe llamarse síncronamente antes del registro blockchain.
        """
        self.ensure_one()
        
        # 1. Verificar si ya existe para evitar duplicados
        existing = self._get_immutable_certificate_attachment()
        if existing:
            _logger.info("Certificado inmutable ya existe (ID: %s). Recalculando hash...", existing.id)
            pdf_content = base64.b64decode(existing.datas)
            hash_hex = hashlib.sha256(pdf_content).hexdigest()
            if self.blockchain_certificate_hash != hash_hex:
                 self.write({'blockchain_certificate_hash': hash_hex})
            return hash_hex

        # 2. Generar Reporte PDF
        try:
            # Usar llamada directa al motor de reportes con el XML ID correcto
            # 'survey.certification_report' es el ID estándar usado por el controlador original
            pdf_content, _ = self.env['ir.actions.report'].sudo()._render_qweb_pdf(
                'survey.certification_report', 
                [self.id], 
                data={'report_type': 'pdf'}
            )
            
            # --- CLEANUP SIDE EFFECT ---
            # El reporte 'survey.certification_report' tiene configurado attachment='certification.pdf'.
            # Al llamar a _render_qweb_pdf, Odoo crea automáticamente ese adjunto.
            # Debemos eliminarlo para evitar duplicados "basura" en el chatter.
            side_effect_attachment = self.env['ir.attachment'].sudo().search([
                ('res_model', '=', 'survey.user_input'),
                ('res_id', '=', self.id),
                ('name', '=', 'certification.pdf')
            ])
            if side_effect_attachment:
                _logger.info("Eliminando adjunto duplicado automático: %s", side_effect_attachment.name)
                side_effect_attachment.unlink()
            # ---------------------------
            
            # 3. Guardar como adjunto permanente
            start_date = fields.Date.today()
            attachment_name = f"Certificado_{self.survey_id.title}_{self.partner_id.name}_{start_date}.pdf".replace('/', '_').replace(' ', '_')
            
            attachment = self.env['ir.attachment'].create({
                'name': attachment_name,
                'type': 'binary',
                'datas': base64.b64encode(pdf_content),
                'res_model': 'survey.user_input',
                'res_id': self.id,
                'mimetype': 'application/pdf',
                'description': 'Certificado Blockchain Inmutable'
            })
            
            # 4. Calcular y guardar Hash
            hash_hex = hashlib.sha256(pdf_content).hexdigest()
            self.write({'blockchain_certificate_hash': hash_hex})
            
            _logger.info("PDF inmutable generado y guardado (Adjunto ID: %s, Hash: %s)", attachment.id, hash_hex)
            return hash_hex
            
        except Exception as e:
            _logger.error("Error FATAL generando certificado inmutable: %s", e, exc_info=True)
            # No devolver fallback aquí si es una generación explícita, mejor fallar para notificar error
            # Si esto falla, el _mark_done atrapará el error y no registrará en blockchain
            raise e

    def _compute_blockchain_hash(self):
        """
        Método llamado por el mixin de blockchain.
        Devuelve el hash pre-calculado almacenado en el campo.
        """
        self.ensure_one()
        if self.blockchain_certificate_hash:
            return self.blockchain_certificate_hash
            
        # Fallback: Intentar generar si no existe (ej. reintento manual)
        try:
            hash_generated = self._generate_and_store_certificate()
            if hash_generated:
                return hash_generated
        except Exception:
            _logger.error("No se pudo generar el hash del certificado para blockchain. ID: %s", self.id)
            
        # Si no hay hash y no se pudo generar, NO RETORNAR NADA (False/None).
        # Esto hará que action_blockchain_register falle o no haga nada, dependiendo del core,
        # pero EVITA registrar un hash basura.
        raise UserError(_("No se ha generado el certificado PDF. No es posible registrar en Blockchain sin el documento inmutable."))


    def _has_purchased_blockchain_variant(self, channel):
        if not self.partner_id or not channel.product_id:
            return False

        attr_name = 'Certificación Blockchain'
        attr_val_name = 'Certificado Blockchain'
        
        domain = [
            ('order_partner_id', '=', self.partner_id.id),
            ('state', 'in', ['sale', 'done']),
            ('product_id.product_tmpl_id', '=', channel.product_id.product_tmpl_id.id)
        ]
        
        sale_lines = self.env['sale.order.line'].sudo().search(domain)
        
        for line in sale_lines:
            for ptav in line.product_id.product_template_attribute_value_ids:
                if (ptav.attribute_id.name.lower() == attr_name.lower() and 
                    ptav.name.lower() == attr_val_name.lower()):
                    return True
        return False

    def _should_certify_on_blockchain(self):
        self.ensure_one()
        
        slides = self.env['slide.slide'].search([
            ('survey_id', '=', self.survey_id.id),
            ('slide_category', '=', 'certification'),
            ('blockchain_certifiable', '=', True)
        ])
        
        if not slides:
            return False
            
        for slide in slides:
            channel = slide.channel_id
            if not channel.blockchain_certification_enabled:
                continue
                
            if self._has_purchased_blockchain_variant(channel):
                return True
                
        return False

    def _mark_done(self):
        """
        Override para manejar certificaciones blockchain de forma separada.
        Evita la generación de PDFs duplicados por el envío de correos estándar.
        """
        blockchain_records = self.filtered(lambda r: r._should_certify_on_blockchain())
        regular_records = self - blockchain_records
        
        # 1. Procesar registros normales con lógica estándar
        res = super(SurveyUserInput, regular_records)._mark_done()
        
        if not blockchain_records:
            return res
            
        # 2. Procesar registros Blockchain (Custom Logic)
        # Copiamos la lógica base pero modificamos el envío de correo y gestión de reporte
        blockchain_records.write({
            'end_datetime': fields.Datetime.now(),
            'state': 'done',
        })
        
        Challenge_sudo = self.env['gamification.challenge'].sudo()
        badge_ids = []
        blockchain_records._notify_new_participation_subscribers()
        
        for user_input in blockchain_records:
            if user_input.survey_id.certification and user_input.scoring_success:
                
                # --- BLOCKCHAIN PROCESS ---
                try:
                    # A. Generar PDF Inmutable (y borrar duplicados automáticos)
                    user_input._generate_and_store_certificate()
                    # B. Registrar en Blockchain
                    user_input.action_blockchain_register()
                except Exception as e:
                    _logger.error('Error proceso blockchain en _mark_done: %s', e, exc_info=True)

                # --- CUSTOM EMAIL SENDING ---
                # Usamos el adjunto inmutable y enviamos via message_post para evitar
                # que el template genere un NUEVO reporte dinámico.
                if user_input.survey_id.certification_mail_template_id and not user_input.test_entry:
                    template = user_input.survey_id.certification_mail_template_id
                    immutable_att = user_input._get_immutable_certificate_attachment()
                    
                    # Preparar valores del correo
                    email_values = {
                        'email_to': user_input.email or user_input.partner_id.email,
                        'email_from': template.email_from,
                    }
                    # Renderizar asunto y cuerpo
                    subject = template._render_field('subject', [user_input.id])[user_input.id]
                    body = template._render_field('body_html', [user_input.id], compute_lang=True)[user_input.id]
                    
                    # Adjuntar SOLO el inmutable (más adjuntos estáticos del template si los hubiera)
                    attachment_ids = [immutable_att.id] if immutable_att else []
                    
                    # Enviar usando message_post (Nativo: Log en Chatter + Email)
                    # Usamos OdooBot (SUPERUSER_ID) como autor para asegurar que 
                    # el usuario (que es quien ejecuta la acción) reciba la notificación.
                    from odoo import SUPERUSER_ID
                    
                    # Preparar adjuntos (Lista de IDs simple, message_post NO acepta comandos)
                    attachment_ids = [immutable_att.id] if immutable_att else []
                    
                    user_input.with_context(mail_notify_force_send=True).message_post(
                        body=body,
                        subject=subject,
                        author_id=self.env.ref('base.partner_root').id or SUPERUSER_ID,
                        subtype_xmlid='mail.mt_comment',
                        message_type='comment',
                        partner_ids=[user_input.partner_id.id] if user_input.partner_id else [],
                        attachment_ids=attachment_ids,
                    )

                if user_input.survey_id.certification_give_badge:
                    badge_ids.append(user_input.survey_id.certification_badge_id.id)

            # Update predefined_question_id to remove inactive questions
            user_input.predefined_question_ids -= user_input._get_inactive_conditional_questions()

        # Gamification Update (Standard)
        if badge_ids:
            challenges = Challenge_sudo.search([('reward_id', 'in', badge_ids)])
            if challenges:
                Challenge_sudo._cron_update(ids=challenges.ids, commit=False)
                
        return res
