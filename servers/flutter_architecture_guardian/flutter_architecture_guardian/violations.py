from dataclasses import dataclass

# Kept in its own module rather than folded into one of the rule modules, since both
# clean_architecture_rules.py and feature_first_rules.py build lists of it.
# rule is one of: "domain_imports_presentation" | "domain_imports_data"
#                | "presentation_imports_data" | "cross_feature_import"
Rule = str


@dataclass
class Violation:
    file: str
    imported_file: str
    rule: Rule
    message: str
