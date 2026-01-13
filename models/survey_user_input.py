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


    def _should_certify_on_blockchain(self):
        """
        Determina si este intento debe ser registrado en blockchain.
        Validación estricta basada en el slide de origen y los derechos de inscripción.
        """
        self.ensure_one()
        
        # 1. Validación de Contexto: Debe venir de un Slide específico
        if not self.slide_id:
            return False
            
        # 2. Validación del Slide: Debe ser certificable
        if self.slide_id.slide_category != 'certification' or not self.slide_id.blockchain_certifiable:
            return False
            
        # 3. Validación del Canal: Debe tener la feature activa
        channel = self.slide_id.channel_id
        if not channel.blockchain_certification_enabled:
            return False
            
        # 4. Validación de Derechos de Inscripción (Enrollment)
        # Buscamos la inscripción específica del usuario en este curso.
        # Esto desacopla la lógica de ventas y soporta cursos gratuitos o becados.
        enrollment = self.env['slide.channel.partner'].sudo().search([
            ('channel_id', '=', channel.id),
            ('partner_id', '=', self.partner_id.id)
        ], limit=1)
        
        if not enrollment:
            return False
            
        # 5. Check Final: ¿Tiene derechos explícitos para este curso?
        if enrollment.blockchain_certification_rights:
            _logger.info("Blockchain Certification Approved for %s in Course %s", self.partner_id.name, channel.name)
            return True
        else:
            _logger.info("Blockchain Certification Denied for %s in Course %s (No Rights)", self.partner_id.name, channel.name)
            return False

    def _mark_done(self):
        """
        Override para manejar certificaciones blockchain de forma separada.
        """
        # 1. Separar flujos
        blockchain_records = self.filtered(lambda r: r._should_certify_on_blockchain())
        regular_records = self - blockchain_records
        
        # 2. Procesar registros NORMALES (Lógica nativa completa)
        res = super(SurveyUserInput, regular_records)._mark_done()
        
        if not blockchain_records:
            return res
            
        # 3. Procesar registros BLOCKCHAIN (Lógica Mirror + Custom)
        # Replicamos la lógica de _mark_done pero controlando el email
        blockchain_records.write({
            'state': 'done',
            'end_datetime': fields.Datetime.now(),
        })
        
        for user_input in blockchain_records:
            # Gamification (Standard Logic Replication)
            if user_input.scoring_success:
                if hasattr(user_input, '_check_certification_badges'):
                    user_input._check_certification_badges()
                
                # --- BLOCKCHAIN PROCESS ---
                try:
                    user_input._generate_and_store_certificate()
                    user_input.action_blockchain_register()
                except Exception as e:
                    _logger.error('Error bloqueo proceso blockchain: %s', e, exc_info=True)

                # --- CUSTOM EMAIL SENDING ---
                # Enviamos email usando el template, pero interceptamos el mail creado
                # para inyectar el PDF inmutable antes de enviarlo.
                if user_input.survey_id.certification_mail_template_id and not user_input.test_entry:
                    template = user_input.survey_id.certification_mail_template_id
                    immutable_att = user_input._get_immutable_certificate_attachment()
                    
                    try:
                        # 1. Crear el mail sin enviarlo (force_send=False)
                        # Esto genera el mail usando toda la lógica estándar (idiomas, destinatarios)
                        mail_id = template.send_mail(user_input.id, force_send=False, raise_exception=True)
                        
                        if mail_id:
                            mail = self.env['mail.mail'].sudo().browse(mail_id)
                            
                            # Validar destinatario para log antes de que se borre el mail
                            email_to_log = mail.email_to or (mail.recipient_ids.mapped('name') if mail.recipient_ids else "Unknown")
                            
                            # 2. Reemplazar adjuntos: Forzar SOLO el inmutable
                            # Detectar y borrar adjuntos "basura" generados por el template (el reporte dinámico)
                            # para que no ensucien el chatter ni se envíen.
                            garbage_attachments = mail.attachment_ids
                            
                            if immutable_att:
                                # Reemplazamos los adjuntos del mail por el nuestro
                                mail.write({
                                    'attachment_ids': [(6, 0, [immutable_att.id])]
                                })
                                # Eliminamos los anteriores de la base de datos
                                if garbage_attachments:
                                    # Filtramos para no borrar el inmutable si por azar estuviera ahí
                                    to_delete = garbage_attachments - immutable_att
                                    if to_delete:
                                        _logger.info("Eliminando %s adjuntos duplicados generados por el template.", len(to_delete))
                                        to_delete.unlink()
                                
                                _logger.info("Adjunto inmutable inyectado en mail ID: %s", mail_id)
                            
                            # 3. Enviar ahora
                            mail.send(raise_exception=True)
                            _logger.info("Email Blockchain enviado exitosamente a: %s", email_to_log)
                        else:
                            _logger.warning("Template.send_mail no retornó ID para el usuario %s", user_input.id)
                        
                    except Exception as email_error:
                        _logger.error("Error enviando email blockchain: %s", email_error, exc_info=True)

        return res
