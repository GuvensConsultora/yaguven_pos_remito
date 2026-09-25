{
    "name": "POS · Remitos a facturar",
    "version": "20.0.1.1.1",
    "summary": "Entregar con remito desde la caja y facturar después desde cualquier sucursal",
    "description": """
Entregar mercadería con remito desde la caja, a clientes autorizados, y facturar los
remitos pendientes después desde la caja de CUALQUIER sucursal.

- El remito es un pedido de venta confirmado con su entrega validada y numerada como
  remito argentino (l10n_ar_stock): el stock sale en el momento.
- Sólo clientes con «Autorizado a remito»; los remitos sin facturar suman al límite de
  crédito que ya usa la cuenta corriente (yaguven_pos_cta_cte).
- «Facturar remitos» trae a la venta de caja todos los pedidos pendientes del cliente con el
  mecanismo nativo de pos_sale: una factura, y lo facturado no vuelve a aparecer.
- Tablero «Remitos a facturar» por sucursal, cliente y días sin facturar.

Diseño acordado con el usuario el 25/09/2026 (fuente/diseno_pos_remito_o20_2026-09-25.md).
""",
    "author": "Yagüven C.G.",
    "website": "https://yaguven.com",
    "category": "Point of Sale",
    "license": "LGPL-3",
    "depends": ["pos_sale", "l10n_ar_stock", "yaguven_pos_cta_cte", "yaguven_operating_unit"],
    "data": [
        "views/res_partner_views.xml",
        "views/sale_order_views.xml",
    ],
    "assets": {
        "point_of_sale._assets_pos": [
            "yaguven_pos_remito/static/src/scss/remito.scss",
            "yaguven_pos_remito/static/src/js/control_buttons.js",
            "yaguven_pos_remito/static/src/xml/control_buttons.xml",
        ],
    },
    "installable": True,
    "application": False,
}
