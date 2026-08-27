import os

# Directory/file markers, inside another feature's directory, that a cross-feature import is
# allowed to reach -- e.g. `lib/features/checkout/public/cart_summary.dart` is fair game for
# other features, but `lib/features/checkout/internal/discount_engine.dart` is not. A feature's
# own `<feature>/<feature>.dart` barrel file is always allowed in addition to these.
PUBLIC_API_MARKERS = [
    marker.strip()
    for marker in os.environ.get("FLUTTER_ARCHITECTURE_GUARDIAN_PUBLIC_MARKERS", "public,api").split(",")
    if marker.strip()
]
