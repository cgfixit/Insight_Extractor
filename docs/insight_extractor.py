import re

# Enhanced Porter-like stemmer: optimized for technical/ML/AI vocabulary

def enhanced_porter_like_stem(word):
    """
    Enhanced rule-based stemmer for English.
    Optimized for technical/ML vocabulary with safe, minimal overstemming.
    Merged from Porter stemmer (broad coverage) and custom rules (precise plurals, safety checks).
    """
    word = word.lower()
    
    # Early return for very short words
    if len(word) <= 3:
        return word
    
    # Step 1a: Plurals (detailed order/rules for accuracy)
    if word.endswith('sses'):
        return word[:-2]  # caresses -> caress
    if word.endswith('ies') and len(word) > 4:
        return word[:-3] + 'y'  # studies -> study
    if word.endswith('es') and len(word) > 4:
        # Check if -es is actual suffix (after sxzh or ch)
        if word[-3] in 'sxzh' or (len(word) > 5 and word[-4:-2] == 'ch'):
            return word[:-2]  # boxes -> box, watches -> watch
        return word[:-1]  # values -> value
    if word.endswith('ss'):
        return word  # caress -> caress
    if word.endswith('s') and not word.endswith(('ss', 'us', 'is')):
        return word[:-1]  # networks -> network
    
    # Step 1b: -ing, -ed (verb forms)
    if word.endswith('ing') and len(word) > 5:
        return word[:-3]  # training -> train
    if word.endswith('ed') and len(word) > 4:
        return word[:-2]  # trained -> train
    
    # Step 2: Common suffixes
    suffixes = [
        ('ational', 'ate'), ('tional', 'tion'), ('enci', 'ence'),
        ('anci', 'ance'), ('izer', 'ize'), ('alli', 'al'),
        ('entli', 'ent'), ('eli', 'e'), ('ousli', 'ous'),
        ('ization', 'ize'), ('ation', 'ate'), ('ator', 'ate'),
        ('alism', 'al'), ('iveness', 'ive'), ('fulness', 'ful'),
        ('ousness', 'ous'), ('aliti', 'al'), ('iviti', 'ive'),
        ('biliti', 'ble'), ('ness', ''), ('ment', ''),
        ('ful', ''), ('less', ''), ('ive', ''), ('ous', ''),
        ('ant', ''), ('ent', ''), ('ism', ''), ('ate', ''),
        ('iti', ''), ('al', ''), ('er', ''), ('ic', ''),
        ('able', ''), ('ible', ''), ('ly', '')
    ]
    
    for suffix, replacement in suffixes:
        if word.endswith(suffix) and len(word) > len(suffix) + 2:
            return word[:-len(suffix)] + replacement
    
    return word


# Load keywords and stem them
try:
    with open('insight_keywords.txt', 'r', encoding='utf-8') as f:
        # FIXED: Skip lines starting with # (comments)
        raw_keywords = [k.strip().lower() for k in f.readlines() 
                       if k.strip() and not k.strip().startswith('#')]
    
    keywords = {enhanced_porter_like_stem(k) for k in raw_keywords}
    print(f"✓ Loaded {len(raw_keywords)} keywords → {len(keywords)} unique stems")

except FileNotFoundError:
    print("✗ insight_keywords.txt not found")
    keywords = set()


# Load conversation thread
try:
    with open('ai_thread.txt', 'r', encoding='utf-8') as f:
        thread = f.read().strip()
    print("✓ Loaded ai_thread.txt")

except FileNotFoundError:
    print("✗ ai_thread.txt not found")
    print("  Create a file named 'ai_thread.txt' with your conversation")
    exit(1)


# Process thread and extract insights
lines = thread.split('\n')
metadata_pattern = re.compile(r'^(\[.*?\]\s+\w+:)\s+(.*)$')
insights = []

for line in lines:
    line = line.strip()
    if not line:
        continue
    
    # Try to extract message (with or without metadata)
    match = metadata_pattern.match(line)
    if match:
        message = match.group(2)
    else:
        message = line
    
    # Extract words and stem them
    words = re.findall(r'\b\w+\b', message.lower())
    stemmed_words = {enhanced_porter_like_stem(w) for w in words}
    
    # Check for keyword matches
    if keywords and stemmed_words & keywords:
        insights.append(line)


print(f"✓ Extracted {len(insights)} insights from {len(lines)} lines")


# Generate markdown output
output = "# Insights from AI Thread\n\n"
output += "## Summary\n"
output += f"Extracted **{len(insights)}** insights from **{len(lines)}** sentences.\n\n"
output += "## Extracted Insights\n\n"

for idx, insight in enumerate(insights, 1):
    output += f"### Insight {idx}\n"
    output += f"> {insight}\n\n"


# Write output file
with open('insights.md', 'w', encoding='utf-8') as f:
    f.write(output)

print(f"✓ Generated insights.md")
print(f"  → {len(insights)} insights extracted")
