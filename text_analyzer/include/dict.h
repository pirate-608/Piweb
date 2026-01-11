#ifndef DICT_H
#define DICT_H

#include <stddef.h>

#define MAX_WORD_LEN 64
#define HASH_TABLE_SIZE 8192

typedef struct Node {
    char word[MAX_WORD_LEN];
    int count;
    struct Node* next;
} Node;

typedef struct {
    Node* buckets[HASH_TABLE_SIZE];
    int unique_count;
    int total_count;
} Dict;

typedef struct {
    char word[MAX_WORD_LEN];
    int count;
} WordFreq;

unsigned long hash(const char* str);
Dict* dict_create(void);
void dict_free(Dict* d);
int dict_add(Dict* d, const char* word);
int dict_get(Dict* d, const char* word);
void dict_get_top(Dict* d, WordFreq* out_arr, int n);

#endif