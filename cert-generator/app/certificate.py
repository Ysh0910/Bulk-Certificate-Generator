import os
import textwrap
from datetime import datetime
from typing import Any, Dict, Optional
from PIL import Image, ImageDraw, ImageFont


class InvalidRecipientError(ValueError):
    """Raised when recipient information is missing or invalid."""
    pass


def _get_font(size: int, bold: bool = False, italic: bool = False) -> ImageFont.ImageFont:
    """Attempt to load serif fonts, falling back gracefully to default PIL font."""
    candidates = []
    if bold and italic:
        candidates = ["DejaVuSerif-BoldItalic.ttf", "timesbi.ttf", "georgiaz.ttf"]
    elif bold:
        candidates = ["DejaVuSerif-Bold.ttf", "timesbd.ttf", "georgiab.ttf"]
    elif italic:
        candidates = ["DejaVuSerif-Italic.ttf", "timesi.ttf", "georgiai.ttf"]
    else:
        candidates = ["DejaVuSerif.ttf", "times.ttf", "georgia.ttf"]

    # System and cross-platform fallbacks
    candidates += ["arial.ttf", "DejaVuSans.ttf", "Helvetica.ttf"]

    for font_name in candidates:
        try:
            return ImageFont.truetype(font_name, size)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _build_appreciation_sentence(extra_fields: Dict[str, Any]) -> str:
    """Build a natural-reading appreciation sentence, gracefully handling missing fields."""
    units = str(extra_fields.get("units_donated", "")).strip()
    date = str(extra_fields.get("donation_date", "")).strip()
    camp = str(extra_fields.get("camp_name", "")).strip()
    org = str(extra_fields.get("organization", "")).strip()

    # Core action phrase
    if units:
        action = f"for donating {units} of blood"
    else:
        action = "for your generous blood donation"

    # Contextual details
    details = []
    if date:
        details.append(f"on {date}")
    if camp:
        details.append(f"at {camp}")
    if org:
        details.append(f"organized by {org}")

    if details:
        sentence = f"{action} {' '.join(details)}, helping save lives in our community."
    else:
        sentence = f"{action}, helping save lives in our community."

    return sentence


def generate_certificate(
    recipient_name: str,
    extra_fields: Optional[Dict[str, Any]],
    output_path: str,
    template_path: str,
) -> None:
    """Generate a high-resolution, landscape Certificate of Appreciation PDF for blood donors.

    Parameters:
        recipient_name: Donor's full name. Must not be empty or whitespace.
        extra_fields: Optional dictionary containing donation metadata:
                      - 'blood_group' (e.g. 'O+')
                      - 'donation_date' (e.g. '2026-10-05')
                      - 'camp_name' (e.g. 'City Blood Donation Camp')
                      - 'organization' (e.g. 'Red Cross Bangalore')
                      - 'units_donated' (e.g. '1 unit')
        output_path: Destination path where the final PDF file is saved.
        template_path: Path to template image (ignored in favor of procedural drawing).

    Raises:
        InvalidRecipientError: If recipient_name is empty or whitespace.
    """
    # Validation check: must be performed before any drawing logic
    if not recipient_name or not recipient_name.strip():
        raise InvalidRecipientError("Recipient name cannot be empty or missing.")

    fields = extra_fields or {}

    # template_path is intentionally ignored: the certificate is drawn entirely via procedural code
    _ = template_path

    # ==================== CANVAS & PALETTE ====================
    canvas_width = 1600
    canvas_height = 1130

    color_bg = (253, 250, 244)          # Warm cream / off-white
    color_maroon = (139, 0, 0)          # Deep blood red / maroon
    color_dark_text = (28, 28, 28)      # Charcoal for donor name
    color_body_text = (55, 65, 81)      # Slate gray for body sentence
    color_muted = (107, 114, 128)       # Subdued gray for subtitles & labels
    color_badge_bg = (255, 243, 243)    # Pale rose for blood group badge

    img = Image.new("RGB", (canvas_width, canvas_height), color=color_bg)
    draw = ImageDraw.Draw(img)

    center_x = canvas_width // 2

    # ==================== 1. DECORATIVE BORDERS ====================
    outer_inset = 40
    inner_inset = 55  # 15px further inset

    draw.rectangle(
        [(outer_inset, outer_inset), (canvas_width - outer_inset, canvas_height - outer_inset)],
        outline=color_maroon,
        width=5,
    )
    draw.rectangle(
        [(inner_inset, inner_inset), (canvas_width - inner_inset, canvas_height - inner_inset)],
        outline=color_maroon,
        width=2,
    )

    # ==================== 2. BLOOD-DROP TEARDROP ICON ====================
    drop_cx = center_x
    drop_tip_y = 95
    drop_base_y = 150
    drop_radius = 22

    # Lower circle
    draw.ellipse(
        [(drop_cx - drop_radius, drop_base_y - drop_radius), (drop_cx + drop_radius, drop_base_y + drop_radius)],
        fill=color_maroon,
    )
    # Upper triangular teardrop peak
    draw.polygon(
        [(drop_cx, drop_tip_y), (drop_cx - 20, drop_base_y - 2), (drop_cx + 20, drop_base_y - 2)],
        fill=color_maroon,
    )
    # Subtle inner specular highlight
    draw.ellipse(
        [(drop_cx - 9, drop_base_y - 8), (drop_cx - 2, drop_base_y)],
        fill=(255, 128, 128),
    )

    # ==================== 3. HEADING & SUBHEADING ====================
    heading_y = 225
    heading_font = _get_font(58, bold=True)
    draw.text((center_x, heading_y), "CERTIFICATE OF APPRECIATION", fill=color_maroon, font=heading_font, anchor="mm")

    subheading_y = 285
    subheading_font = _get_font(26, italic=True)
    draw.text(
        (center_x, subheading_y),
        "Presented in recognition of a generous blood donation",
        fill=color_muted,
        font=subheading_font,
        anchor="mm",
    )

    # ==================== 4. BODY & RECIPIENT ====================
    intro_y = 380
    intro_font = _get_font(24)
    draw.text((center_x, intro_y), "This certificate is proudly presented to", fill=color_muted, font=intro_font, anchor="mm")

    name_y = 470
    name_font = _get_font(70, bold=True)
    draw.text((center_x, name_y), recipient_name.strip(), fill=color_dark_text, font=name_font, anchor="mm")

    # Decorative underline with centered diamond
    underline_y = 525
    underline_half_w = 260
    draw.line([(center_x - underline_half_w, underline_y), (center_x + underline_half_w, underline_y)], fill=color_maroon, width=2)
    draw.polygon(
        [(center_x, underline_y - 5), (center_x + 6, underline_y), (center_x, underline_y + 5), (center_x - 6, underline_y)],
        fill=color_maroon,
    )

    # Assembled body sentence (wrapped gracefully)
    body_sentence = _build_appreciation_sentence(fields)
    wrapped_lines = textwrap.wrap(body_sentence, width=68)
    body_font = _get_font(28)
    body_start_y = 600
    line_spacing = 42

    for idx, line in enumerate(wrapped_lines):
        curr_y = body_start_y + (idx * line_spacing)
        draw.text((center_x, curr_y), line, fill=color_body_text, font=body_font, anchor="mm")

    # ==================== 5. FOOTER & GRAPHICS ====================
    # A. Decorative circular seal on bottom-left
    seal_cx = 210
    seal_cy = 960
    draw.ellipse([(seal_cx - 52, seal_cy - 52), (seal_cx + 52, seal_cy + 52)], outline=color_maroon, width=4)
    draw.ellipse([(seal_cx - 42, seal_cy - 42), (seal_cx + 42, seal_cy + 42)], outline=color_maroon, width=2)
    draw.ellipse([(seal_cx - 18, seal_cy - 18), (seal_cx + 18, seal_cy + 18)], fill=color_maroon)

    # B. Two signature areas side by side
    sig_font = _get_font(20)
    sig_line_half_w = 120
    sig_line_y = 960
    sig_label_y = 988

    # Left signature: Authorized Signatory
    sig_left_cx = 620
    draw.line([(sig_left_cx - sig_line_half_w, sig_line_y), (sig_left_cx + sig_line_half_w, sig_line_y)], fill=color_muted, width=2)
    draw.text((sig_left_cx, sig_label_y), "Authorized Signatory", fill=color_muted, font=sig_font, anchor="mm")

    # Right signature: Date
    sig_right_cx = 1040
    date_val = str(fields.get("donation_date", "")).strip()
    if not date_val:
        date_val = datetime.now().strftime("%B %d, %Y")
    date_label = f"Date: {date_val}"

    draw.line([(sig_right_cx - sig_line_half_w, sig_line_y), (sig_right_cx + sig_line_half_w, sig_line_y)], fill=color_muted, width=2)
    draw.text((sig_right_cx, sig_label_y), date_label, fill=color_muted, font=sig_font, anchor="mm")

    # C. Blood Group badge on bottom-right corner (if provided)
    blood_group = str(fields.get("blood_group", "")).strip()
    if blood_group:
        badge_w = 200
        badge_h = 60
        badge_x0 = canvas_width - inner_inset - 20 - badge_w
        badge_y0 = seal_cy - (badge_h // 2)
        badge_x1 = badge_x0 + badge_w
        badge_y1 = badge_y0 + badge_h

        draw.rectangle([(badge_x0, badge_y0), (badge_x1, badge_y1)], fill=color_badge_bg, outline=color_maroon, width=2)
        badge_font = _get_font(22, bold=True)
        draw.text(
            ((badge_x0 + badge_x1) // 2, (badge_y0 + badge_y1) // 2),
            f"Blood Group: {blood_group}",
            fill=color_maroon,
            font=badge_font,
            anchor="mm",
        )

    # ==================== 6. SAVE TO PDF ====================
    output_dir = os.path.dirname(os.path.abspath(output_path))
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    img.save(output_path, "PDF")
