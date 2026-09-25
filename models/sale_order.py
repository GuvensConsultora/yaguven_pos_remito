from odoo import _, api, fields, models
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    yaguven_remito_pos = fields.Boolean(
        string='Remito desde caja', readonly=True, copy=False, index=True,
        help='El pedido nació del botón «Remito» de la caja: la mercadería ya se entregó y '
             'queda pendiente de facturar.')
    yaguven_remito_config_id = fields.Many2one(
        'pos.config', string='Caja del remito', readonly=True, copy=False)
    yaguven_remito_numero = fields.Char(
        string='N° de remito', compute='_compute_yaguven_remito_numero', store=True)
    yaguven_dias_sin_facturar = fields.Integer(
        string='Días sin facturar', compute='_compute_yaguven_dias_sin_facturar')

    @api.depends('picking_ids.l10n_ar_delivery_guide_number', 'picking_ids.state')
    def _compute_yaguven_remito_numero(self):
        for so in self:
            hechos = so.picking_ids.filtered(lambda p: p.state == 'done')
            so.yaguven_remito_numero = ', '.join(
                n for n in hechos.mapped('l10n_ar_delivery_guide_number') if n) or False

    def _compute_yaguven_dias_sin_facturar(self):
        hoy = fields.Date.context_today(self)
        for so in self:
            if so.invoice_status == 'invoiced' or not so.date_order:
                so.yaguven_dias_sin_facturar = 0
            else:
                so.yaguven_dias_sin_facturar = (hoy - so.date_order.date()).days

    # ------------------------------------------------------------------
    # Caja: «Remito»
    # ------------------------------------------------------------------
    @api.model
    def yaguven_crear_remito_desde_pos(self, config_id, partner_id, lineas):
        """Crea el remito de una venta de caja: pedido confirmado + entrega validada y
        numerada como remito argentino. Todo o nada: si algo falla, no queda nada.

        `lineas` = [{'product_id', 'qty', 'price_unit', 'discount'}] tal como las tiene
        la venta en la caja (el precio ya viene con la lista de precios aplicada).
        Devuelve lo que la caja necesita para imprimir y avisar.
        """
        config = self.env['pos.config'].browse(config_id)
        partner = self.env['res.partner'].browse(partner_id)
        comercial = partner.commercial_partner_id
        if not partner.exists() or not comercial.yaguven_remito_autorizado:
            raise UserError(_(
                'El cliente %(cliente)s no está autorizado a llevar mercadería con remito.\n\n'
                'Se autoriza en la ficha del cliente: «Autorizado a remito».',
                cliente=partner.display_name))
        lineas = [l for l in (lineas or []) if l.get('qty')]
        if not lineas:
            raise UserError(_('El remito no tiene productos.'))
        if any(l['qty'] < 0 for l in lineas):
            raise UserError(_('Un remito no puede llevar cantidades negativas (devoluciones).'))

        almacen = config.picking_type_id.warehouse_id
        pedido = self.with_company(config.company_id).create({
            'partner_id': partner.id,
            'company_id': config.company_id.id,
            'warehouse_id': almacen.id,
            'yaguven_remito_pos': True,
            'yaguven_remito_config_id': config.id,
            'order_line': [(0, 0, {
                'product_id': l['product_id'],
                'product_uom_qty': l['qty'],
                'price_unit': l['price_unit'],
                'discount': l.get('discount') or 0.0,
            }) for l in lineas],
        })

        # Tope: el remito nuevo contra lo que le queda (límite − deuda − remitos sin
        # facturar). El pedido recién creado está en borrador: todavía no suma en los
        # pendientes, así que no se cuenta dos veces.
        disponible = partner._yaguven_credito_disponible()
        if disponible is not None:
            if pedido.amount_total > disponible:
                raise UserError(_(
                    'El remito de %(importe)s supera el crédito disponible de %(cliente)s '
                    '(%(disponible)s, contando la deuda y los remitos sin facturar).',
                    importe=pedido.currency_id.format(pedido.amount_total),
                    cliente=comercial.display_name,
                    disponible=pedido.currency_id.format(max(disponible, 0.0))))

        pedido.action_confirm()
        entrega = pedido.picking_ids.filtered(lambda p: p.state not in ('done', 'cancel'))
        for mov in entrega.move_ids:
            mov.quantity = mov.product_uom_qty
            mov.picked = True
        entrega.with_context(skip_backorder=True, cancel_backorder=True, skip_sms=True).button_validate()
        if entrega.filtered(lambda p: p.state != 'done'):
            raise UserError(_('No se pudo validar la entrega del remito.'))

        numerados = entrega.filtered(lambda p: p.picking_type_id.l10n_ar_document_type_id)
        if numerados:
            numerados.l10n_ar_action_create_delivery_guide()
        reporte = 'l10n_ar_stock.report_delivery_guide' if numerados else 'stock.report_deliveryslip'
        return {
            'pedido_id': pedido.id,
            'pedido': pedido.name,
            'remito': pedido.yaguven_remito_numero or entrega[:1].name,
            'importe': pedido.amount_total,
            'reporte_url': '/report/pdf/%s/%s' % (reporte, ','.join(str(i) for i in entrega.ids)),
        }

    # ------------------------------------------------------------------
    # Caja: «Facturar remitos»
    # ------------------------------------------------------------------
    @api.model
    def yaguven_remitos_pendientes(self, partner_id):
        """Ids de los remitos del cliente pendientes de facturar, del más viejo al más nuevo."""
        comercial = self.env['res.partner'].browse(partner_id).commercial_partner_id
        return self.search(
            self.env['res.partner']._yaguven_dominio_remitos_pendientes(comercial),
            order='date_order, id').ids
