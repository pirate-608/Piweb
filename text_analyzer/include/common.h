#ifndef COMMON_H
#define COMMON_H

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

#define MAX_WORD_LEN 64       // 单个词最大长度
#define MAX_SECTIONS 100      // 最大章节数
#define HASH_TABLE_SIZE 8192  // 哈希桶大小，适合万字级别文本

typedef enum {
    LANG_UNKNOWN = 0,
    LANG_EN,
    LANG_CN
} Language;

#endif