// polycell: urn=urn:wm:cell:shop:pricing.quote:v1 contract=db6ace1e979b
// Komórka logiki (Rust - gorąca ścieżka obliczeniowa). Czysta funkcja: bez I/O, bez transportu.
use crate::types::*;

fn round2(x: f64) -> f64 {
    (x * 100.0).round() / 100.0
}

fn tax_rate(currency: &str) -> Result<f64, String> {
    match currency {
        "PLN" => Ok(0.23),
        "EUR" => Ok(0.21),
        "USD" => Ok(0.0),
        other => Err(format!("unsupported currency: {other}")),
    }
}

fn coupon_rate(coupon: Option<&str>) -> f64 {
    match coupon {
        Some("AI10") => 0.10,
        Some("AI25") => 0.25,
        _ => 0.0,
    }
}

pub fn run(input: PricingQuoteInput) -> Result<PricingQuoteOutput, String> {
    if input.items.iter().any(|i| i.qty <= 0 || i.unit_price < 0.0) {
        return Err("invalid line item".into());
    }
    let subtotal = round2(input.items.iter().map(|i| i.qty as f64 * i.unit_price).sum());
    let discount = round2(subtotal * coupon_rate(input.coupon.as_deref()));
    let tax = round2((subtotal - discount) * tax_rate(&input.currency)?);
    Ok(PricingQuoteOutput {
        subtotal,
        discount,
        tax,
        total: round2(subtotal - discount + tax),
        currency: input.currency,
    })
}
