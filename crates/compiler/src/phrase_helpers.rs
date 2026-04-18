use domain::{Selector, StringMatchKind, TextSelector};

pub(crate) fn extract_after_any<'a>(input: &'a str, prefixes: &[&str]) -> Option<&'a str> {
    prefixes
        .iter()
        .find_map(|prefix| input.strip_prefix(prefix).map(trim_selector_phrase))
}

pub(crate) fn extract_text_entry(input: &str) -> Option<(String, String)> {
    for prefix in [
        "the user enters ",
        "user enters ",
        "the user types ",
        "user types ",
    ] {
        if let Some(rest) = input.strip_prefix(prefix) {
            let (text, remainder) = extract_quoted_value(rest)?;
            let target = remainder
                .strip_prefix("into ")
                .or_else(|| remainder.strip_prefix("in "))
                .map(trim_selector_phrase)?;
            return Some((text, target.to_string()));
        }
    }
    None
}

pub(crate) fn extract_text_equals_assertion(input: &str) -> Option<(String, String)> {
    let target = input.strip_suffix(" is displayed")?;
    let (value, remaining) = extract_quoted_value(target)?;
    if remaining.is_empty() {
        Some((value.clone(), value))
    } else {
        None
    }
}

pub(crate) fn extract_quoted_value(input: &str) -> Option<(String, &str)> {
    let trimmed = input.trim();
    let rest = trimmed.strip_prefix('"')?;
    let quote_end = rest.find('"')?;
    let value = rest[..quote_end].to_string();
    let remainder = rest[quote_end + 1..].trim();
    Some((value, remainder))
}

pub(crate) fn phrase_to_selector(input: &str) -> Selector {
    Selector::Text(TextSelector {
        value: humanize_selector_phrase(trim_selector_phrase(input)),
        match_kind: StringMatchKind::Contains,
    })
}

pub(crate) fn trim_selector_phrase(input: &str) -> &str {
    input
        .trim()
        .trim_end_matches(" field")
        .trim_end_matches(" button")
        .trim_end_matches('.')
        .trim()
}

pub(crate) fn humanize_selector_phrase(input: &str) -> String {
    input
        .split_whitespace()
        .filter_map(|word| match word {
            "the" => None,
            "screen" => None,
            other => Some(other),
        })
        .collect::<Vec<_>>()
        .join(" ")
}

pub(crate) fn normalize_phrase(input: &str) -> String {
    input
        .trim()
        .trim_end_matches('.')
        .split_whitespace()
        .collect::<Vec<_>>()
        .join(" ")
        .to_lowercase()
}

pub(crate) fn slugify(input: &str) -> String {
    let mut output = String::new();
    let mut last_dash = false;
    for c in input.chars().flat_map(|c| c.to_lowercase()) {
        if c.is_ascii_alphanumeric() {
            output.push(c);
            last_dash = false;
        } else if !last_dash {
            output.push('-');
            last_dash = true;
        }
    }
    output.trim_matches('-').to_string()
}
