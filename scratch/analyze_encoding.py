
text = "㫰쬉찮촊㫥팠⃪伊楲楧慮㩬吠敨圠牡楲戎䄠灰敲瑮捩켊›⻀픠ऺ楄楧൧윊㫠圠楨整潗汯൦ഊ퐊㫲㏰ㄠ㠲㫬㜉㐶찠숊￬㫿ㄉ㨳〳⳧⃮⳨ﳰ⃮ⷧ￨ﴠ⃥⃮⃢ﻨ⃭⃑￫⃠⃨ₗ⃥ﳱﴠﳫ⃥￨⳥찠⃥ﻳ麟ﳫ⃩툠⃥⃮⃬⃤ﳫﳲⳢ⃬ﯭ쌠ﳲ￬霠촠⸮മꤊ琠癥獡￠￫⃨⃮⃬⃩ⳬ⃨﯂⃥술⻨"
for char in text[:20]:
    print(f"U+{ord(char):04X}")

# Try to decode "伊楲楧慮㩬"
snippet = "伊楲楧慮㩬"
try:
    # Try interpreting as UTF-16BE bytes
    be_bytes = snippet.encode('utf-16-be')
    print(f"BE bytes: {be_bytes.hex(' ')}")
    print(f"As ASCII/UTF-8 (BE): {be_bytes.decode('utf-8', errors='replace')}")
except Exception as e:
    print(f"BE error: {e}")

try:
    # Try interpreting as UTF-16LE bytes
    le_bytes = snippet.encode('utf-16-le')
    print(f"LE bytes: {le_bytes.hex(' ')}")
    print(f"As ASCII/UTF-8 (LE): {le_bytes.decode('utf-8', errors='replace')}")
except Exception as e:
    print(f"LE error: {e}")
