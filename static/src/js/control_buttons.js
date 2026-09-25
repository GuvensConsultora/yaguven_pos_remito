import { ControlButtons } from "@point_of_sale/app/screens/product_screen/control_buttons/control_buttons";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { AlertDialog, ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { ask } from "@point_of_sale/app/utils/make_awaitable_dialog";

/** El texto del error que manda el servidor (en 20 viaja en error.data.message). */
function mensajeDe(error) {
    return error?.data?.message || error?.message || String(error);
}

patch(ControlButtons.prototype, {
    /**
     * «Remito»: entrega la venta en curso sin cobrarla. El servidor crea el pedido,
     * valida la entrega y la numera como remito; acá sólo se junta lo que hay en la
     * caja, se confirma con el cajero y se imprime.
     */
    async onClickYaguvenRemito() {
        const order = this.pos.getOrder();
        const partner = order?.getPartner();
        const lineas = (order?.getOrderlines() || []).filter((l) => l.qty);
        if (!partner) {
            this.dialog.add(AlertDialog, {
                title: _t("Falta el cliente"),
                body: _t("Elegí el cliente antes de hacer el remito."),
            });
            return;
        }
        if (!partner.yaguven_remito_autorizado) {
            this.dialog.add(AlertDialog, {
                title: _t("Cliente sin remito"),
                body: _t(
                    "%s no está autorizado a llevar mercadería con remito. Se autoriza en la ficha del cliente.",
                    partner.name
                ),
            });
            return;
        }
        if (!lineas.length) {
            this.dialog.add(AlertDialog, {
                title: _t("Remito vacío"),
                body: _t("Agregá los productos que se llevan."),
            });
            return;
        }
        const ok = await ask(this.dialog, {
            title: _t("Entregar con remito"),
            body: _t(
                "Se entrega a %(cliente)s por %(importe)s, sin cobrar. Queda pendiente de facturar y se puede facturar desde cualquier caja.",
                {
                    cliente: partner.name,
                    importe: this.pos.formatCurrency(order.priceIncl),
                }
            ),
            confirmLabel: _t("Hacer remito"),
        });
        if (!ok) {
            return;
        }
        let r;
        try {
            r = await this.pos.data.call("sale.order", "yaguven_crear_remito_desde_pos", [
                this.pos.config.id,
                partner.id,
                lineas.map((l) => ({
                    product_id: l.product_id.id,
                    qty: l.qty,
                    price_unit: l.price_unit,
                    discount: l.discount || 0,
                })),
            ]);
        } catch (error) {
            this.dialog.add(AlertDialog, { title: _t("No se pudo hacer el remito"), body: mensajeDe(error) });
            return;
        }
        window.open(r.reporte_url, "_blank");
        this.notification.add(_t("Remito %s hecho: queda pendiente de facturar.", r.remito), { type: "success" });
        // También del servidor: una venta en borrador que quede ahí traba el cierre de caja.
        this.pos.removeOrder(order);
        this.pos.addNewOrder();
    },

    /**
     * «Facturar remitos»: trae a la venta en curso todos los remitos pendientes del
     * cliente, con el mecanismo nativo de pos_sale (settleSO). Después se cobra y se
     * factura como cualquier venta; lo facturado no vuelve a aparecer.
     */
    async onClickYaguvenFacturarRemitos() {
        const partner = this.pos.getOrder()?.getPartner();
        if (!partner) {
            this.dialog.add(AlertDialog, {
                title: _t("Falta el cliente"),
                body: _t("Elegí el cliente para ver sus remitos pendientes."),
            });
            return;
        }
        const ids = await this.pos.data.call("sale.order", "yaguven_remitos_pendientes", [partner.id]);
        if (!ids.length) {
            this.dialog.add(AlertDialog, {
                title: _t("Sin remitos pendientes"),
                body: _t("%s no tiene remitos pendientes de facturar.", partner.name),
            });
            return;
        }
        for (const id of ids) {
            const so = await this.pos._getSaleOrder(id);
            await this.pos.settleSO(so, so.fiscal_position_id);
        }
        this.notification.add(
            _t("%s remito(s) pendientes cargados en la venta. Cobrá y facturá como siempre.", ids.length),
            { type: "info" }
        );
    },
});
