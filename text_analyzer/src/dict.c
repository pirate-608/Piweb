#include "dict.h"
#include <stdlib.h>
#include <string.h>
#include <stdio.h>

// DJB2 Hash function
unsigned long hash(const char *str) {
    unsigned long hash = 5381;
    int c;
    while ((c = *str++)) hash = ((hash << 5) + hash) + c;
    return hash % HASH_TABLE_SIZE;
}

Dict* dict_create() {
    Dict* d = (Dict*)calloc(1, sizeof(Dict));
    return d;
}

void dict_free(Dict* d) {
    if (!d) return;
    for (int i = 0; i < HASH_TABLE_SIZE; i++) {
        Node* curr = d->buckets[i];
        while (curr) {
            Node* temp = curr;
            curr = curr->next;
            free(temp);
        }
    }
    free(d);
}

int dict_add(Dict* d, const char* word) {
    unsigned long h = hash(word);
    Node* curr = d->buckets[h];
    
    while (curr) {
        if (strncmp(curr->word, word, MAX_WORD_LEN) == 0) {
            d->total_count++;
            return ++(curr->count);
        }
        curr = curr->next;
    }
    
    // New node
    Node* new_node = (Node*)malloc(sizeof(Node));
    strncpy(new_node->word, word, MAX_WORD_LEN - 1);
    new_node->word[MAX_WORD_LEN - 1] = '\0';
    new_node->count = 1;
    new_node->next = d->buckets[h];
    d->buckets[h] = new_node;
    
    d->unique_count++;
    d->total_count++;
    return 1;
}

int dict_get(Dict* d, const char* word) {
    unsigned long h = hash(word);
    Node* curr = d->buckets[h];
    while (curr) {
        if (strncmp(curr->word, word, MAX_WORD_LEN) == 0) return curr->count;
        curr = curr->next;
    }
    return 0;
}

// 简单的冒泡排序取出前N（因为N很小，通常为10，效率足够）
void dict_get_top(Dict* d, WordFreq* out_arr, int n) {
    // 1. Collect all nodes (temporary inefficient but safe)
    int count = 0;
    // Assume worst case for stack alloc or use heap if unique_count is large
    // For safety with large text, we just scan and insert into fixed size sorted array
    
    for (int i = 0; i < n; i++) {
        out_arr[i].count = -1;
        out_arr[i].word[0] = '\0';
    }

    for (int i = 0; i < HASH_TABLE_SIZE; i++) {
        Node* curr = d->buckets[i];
        while (curr) {
            // Insert into top N
            int val = curr->count;
            char* key = curr->word;
            
            for (int k = 0; k < n; k++) {
                if (val > out_arr[k].count) {
                    // Shift
                    for (int j = n - 1; j > k; j--) {
                        out_arr[j] = out_arr[j-1];
                    }
                    out_arr[k].count = val;
                    strcpy(out_arr[k].word, key);
                    break;
                }
            }
            curr = curr->next;
        }
    }
}