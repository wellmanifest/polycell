// polycell: urn=urn:wm:cell:shop:notify.render:v1 contract=f4ff80f6c235
// Komórka logiki (TypeScript). Czysta funkcja, tylko składnia usuwalna (Node --strip-types).
import type { NotifyRenderInput, NotifyRenderOutput } from "../../gen/ts/types.ts";

const T = {
  pl: { subject: "Potwierdzenie zamówienia", body: (n: string, a: string) => `Dzień dobry ${n}, Twoje zamówienie na kwotę ${a} zostało przyjęte.` },
  en: { subject: "Order confirmation", body: (n: string, a: string) => `Hello ${n}, your order for ${a} has been accepted.` },
};

export function run(input: NotifyRenderInput): NotifyRenderOutput {
  const t = input.lang === "pl" ? T.pl : T.en;
  const amount = `${input.total.toFixed(2)} ${input.currency}`;
  return { subject: `${t.subject}: ${amount}`, body: t.body(input.customer_name, amount) };
}
