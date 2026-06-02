import re
import hashlib
import random
import pickle
import numpy as np

from datasketch import MinHash

from config.settings import (
    SHINGLE_K,
    NUM_PERM,
    LARGE_PRIME,
    LOCAL_LSH_INDEX,
)


random.seed(42)
HASH_A = [random.randint(1, LARGE_PRIME - 1) for _ in range(NUM_PERM)]
HASH_B = [random.randint(0, LARGE_PRIME - 1) for _ in range(NUM_PERM)]


def load_lsh_index():
    with open(LOCAL_LSH_INDEX, "rb") as f:
        return pickle.load(f)


def tokenize_words_offline_style(text):
    if not text:
        return []
    return re.findall(r"\w{2,}", text.lower())


def get_shingle_hashes_offline_style(text, k=SHINGLE_K):
    words = tokenize_words_offline_style(text)

    if len(words) < k:
        return set()

    hashes = set()

    for i in range(len(words) - k + 1):
        shingle = " ".join(words[i:i + k])
        h = int(hashlib.md5(shingle.encode()).hexdigest(), 16) % LARGE_PRIME
        hashes.add(h)

    return hashes


def compute_signature_offline_style(text):
    shingle_hashes = get_shingle_hashes_offline_style(text)

    if not shingle_hashes:
        return None

    signature = []

    for i in range(NUM_PERM):
        min_value = LARGE_PRIME

        for h in shingle_hashes:
            v = (HASH_A[i] * h + HASH_B[i]) % LARGE_PRIME
            if v < min_value:
                min_value = v

        signature.append(min_value)

    return signature


def create_query_minhash_offline_style(text):
    signature = compute_signature_offline_style(text)

    if signature is None:
        return None

    m = MinHash(num_perm=NUM_PERM)
    m.hashvalues = np.array(signature, dtype=np.uint64)

    return m


def build_query_text_for_lsh(clean_text, sections):
    intro = sections.get("introduction", "")
    body = sections.get("body", "")

    query_text = " ".join([
        intro if isinstance(intro, str) else "",
        body if isinstance(body, str) else "",
    ]).strip()

    if len(query_text) < 200:
        query_text = clean_text

    return query_text


def query_lsh_candidates(query_text, lsh_index, max_candidates=50):
    query_mh = create_query_minhash_offline_style(query_text)

    if query_mh is None:
        return [], None

    candidates = list(lsh_index.query(query_mh))
    return candidates[:max_candidates], query_mh