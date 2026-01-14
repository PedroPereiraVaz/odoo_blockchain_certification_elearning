# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
import hashlib
import logging
import json
import base64
from markupsafe import Markup

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
        Sobrescribe _mark_done para usar la lógica nativa de Odoo (colas, templates, chatter)
        pero inyectando nuestro PDF inmutable en lugar del dinámico.
        """
        # 1. PROCESO STANDARD
        # Llamamos primero a super para que Odoo calcule puntuaciones y determine si pasó.
        res = super(SurveyUserInput, self)._mark_done()
        
        # 2. LÓGICA BLOCKCHAIN & VISIBILIDAD (Solo si Standard ya terminó)
        # Pre-calculamos IDs necesarios
        comment_subtype_id = self.env.ref('mail.mt_comment').id
        
        for user_input in self:
            # CHECK: Solo procedemos si el intento fue EXITOSO (Aprobó)
            if not user_input.scoring_success:
                continue

            # Determinar si aplica Blockchain
            is_blockchain = user_input._should_certify_on_blockchain()
            
            # --- GENERACIÓN Y REGISTRO BLOCKCHAIN ---
            if is_blockchain:
                try:
                    # Generamos el certificado AHORA, sabiendo que aprobó.
                    user_input._generate_and_store_certificate()
                    # Registramos transacción
                    user_input.action_blockchain_register()
                except Exception as e:
                    _logger.error('Error proceso blockchain en _mark_done: %s', e)

        # 3. POST-PROCESO: Interceptación, Canje y Visibilidad
        for user_input in self:
            # Buscamos el correo recién creado en cola
            last_mail = self.env['mail.mail'].sudo().search([
                ('model', '=', 'survey.user_input'),
                ('res_id', '=', user_input.id),
                ('state', '=', 'outgoing')
            ], order='create_date desc', limit=1)

            is_blockchain = user_input._should_certify_on_blockchain()

            # Caso Blockchain: SWAP + Visibilidad Garantizada
            if is_blockchain and user_input.scoring_success:
                immutable_att = user_input._get_immutable_certificate_attachment()
                
                if immutable_att and last_mail:
                    _logger.info("Interceptado Mail ID %s para inyección (Blockchain).", last_mail.id)
                    
                    # 1. Swap en correo (Lo que le llega al usuario)
                    last_mail.write({'attachment_ids': [(6, 0, [immutable_att.id])]})

                    # 2. Visibilidad Garantizada en Chatter
                    if last_mail.body_html or last_mail.body:
                        user_input.message_post(
                            body=Markup(last_mail.body_html or last_mail.body),
                            attachment_ids=[immutable_att.id],
                            subtype_xmlid='mail.mt_comment',
                            message_type='comment'
                        )
                    
                    # 3. Limpiar basura dinamica
                    garbage = self.env['ir.attachment'].sudo().search([
                        ('res_model', '=', 'survey.user_input'),
                        ('res_id', '=', user_input.id),
                        ('name', '=', 'certification.pdf'),
                        ('id', '!=', immutable_att.id)
                    ])
                    if garbage:
                        garbage.unlink()

            # Caso Standard: Solo Visibilidad + Limpieza Safe
            elif user_input.scoring_success:
                # Visibilidad en Chatter
                # Replicamos el contenido del correo en el chatter si Odoo no lo hizo visible.
                if last_mail and (last_mail.body_html or last_mail.body):
                     user_input.message_post(
                        body=Markup(last_mail.body_html or last_mail.body),
                        # Usamos el adjunto original del correo (debería ser el PDF standard)
                        attachment_ids=[att.id for att in last_mail.attachment_ids],
                        subtype_xmlid='mail.mt_comment',
                        message_type='comment'
                    )

                # Limpieza de duplicados
                garbage_standard = self.env['ir.attachment'].sudo().search([
                    ('res_model', '=', 'survey.user_input'),
                    ('res_id', '=', user_input.id),
                    ('name', '=', 'certification.pdf')
                ])
                for att in garbage_standard:
                    other_count = self.env['ir.attachment'].sudo().search_count([
                        ('res_model', '=', 'survey.user_input'),
                        ('res_id', '=', att.res_id),
                        ('id', '!=', att.id)
                    ])
                    if other_count > 0:
                        _logger.info("Limpieza Standard: Eliminando duplicado ID %s", att.id)
                        att.unlink()

        return res
