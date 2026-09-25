from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    yaguven_remito_autorizado = fields.Boolean(
        string='Autorizado a remito',
        help='Puede llevarse mercadería con remito desde la caja y facturarla después.\n\n'
             'Los remitos sin facturar suman al límite de crédito del cliente (el mismo que '
             'usa la cuenta corriente): si con el remito nuevo lo pasa, la caja no lo emite.')
    yaguven_remitos_pendientes = fields.Monetary(
        string='Remitos sin facturar',
        compute='_compute_yaguven_remitos_pendientes',
        currency_field='currency_id',
        help='Lo entregado con remito y todavía no facturado, con impuestos.')

    def _compute_yaguven_remitos_pendientes(self):
        for partner in self:
            partner.yaguven_remitos_pendientes = partner._yaguven_monto_remitos_pendientes()

    def _yaguven_monto_remitos_pendientes(self):
        """Importe de los remitos sin facturar del cliente, leído EN EL MOMENTO.

        Importe = amount_to_invoice nativo del pedido (con impuestos): en un remito lo
        pedido ya está entregado entero. El tope se controla con esto y no con el campo
        calculado: un campo no guardado queda recordado dentro de la misma operación y,
        con dos remitos seguidos, el segundo veía el valor de antes del primero
        (medido en staging: el tope no frenaba).
        """
        self.ensure_one()
        comercial = self.commercial_partner_id
        if not comercial.id:
            return 0.0
        pedidos = self.env['sale.order'].sudo().search(
            self._yaguven_dominio_remitos_pendientes(comercial))
        pedidos.invalidate_recordset(['amount_to_invoice'])
        return sum(pedidos.mapped('amount_to_invoice'))

    @api.model
    def _yaguven_dominio_remitos_pendientes(self, comercial):
        return [
            ('partner_id', 'child_of', comercial.id),
            ('state', '=', 'sale'),
            ('yaguven_remito_pos', '=', True),
            ('invoice_status', '!=', 'invoiced'),
        ]

    def _yaguven_credito_disponible(self):
        """Lo que le queda al cliente para un remito nuevo, o None si no tiene tope.

        Misma regla que la cuenta corriente (yaguven_pos_cta_cte): límite 0 = sin tope.
        Al saldo contable se le suman los remitos sin facturar, que todavía no están en
        la cuenta del cliente pero ya son mercadería entregada.
        """
        self.ensure_one()
        comercial = self.commercial_partner_id
        if not comercial.use_partner_credit_limit or not comercial.credit_limit:
            return None
        comercial.invalidate_recordset(['credit'])
        return comercial.credit_limit - comercial.credit - comercial._yaguven_monto_remitos_pendientes()

    @api.model
    def _load_pos_data_fields(self, config):
        fields_list = super()._load_pos_data_fields(config)
        if not fields_list:
            return fields_list
        return fields_list + ['yaguven_remito_autorizado', 'yaguven_remitos_pendientes']
