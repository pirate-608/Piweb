#include "common.h"
#include <ctype.h>

#define MIN(a,b) (((a)<(b))?(a):(b))
#define MIN3(a,b,c) MIN(MIN(a,b),c)

// 内部辅助：标准化字符串 (转小写 + 去除首尾空格 + 合并中间空格)
void normalize_string(char* dest, const char* src, size_t dest_size) {
    size_t i = 0, j = 0;
    int space_seen = 0; // 标记是否刚处理过空格

    // 1. 跳过开头的空格
    while (src[i] && isspace((unsigned char)src[i])) {
        i++;
    }

    while (src[i] && j < dest_size - 1) {
        unsigned char c = (unsigned char)src[i];
        
        if (isspace(c)) {
            // 只有当前面没有空格时，才写入一个空格（合并多个空格）
            if (!space_seen) {
                dest[j++] = ' ';
                space_seen = 1;
            }
        } else {
            dest[j++] = tolower(c);
            space_seen = 0;
        }
        i++;
    }

    // 2. 去除末尾可能的空格 (如果字符串全为空格，j可能为0，需注意)
    if (j > 0 && dest[j-1] == ' ') {
        j--;
    }
    
    dest[j] = '\0';
}

// Levenshtein Distance (编辑距离) 算法 - 空间优化版
int levenshtein_distance(const char *s1, const char *s2) {
    int len1 = strlen(s1);
    int len2 = strlen(s2);
    
    // 安全检查：防止数组越界
    if (len1 > MAX_STR_LEN) len1 = MAX_STR_LEN;
    if (len2 > MAX_STR_LEN) len2 = MAX_STR_LEN;

    // 优化：只使用两行数组，将空间复杂度从 O(M*N) 降低到 O(N)
    // 原先 matrix[257][257] 占用约 264KB 栈空间，现在仅需约 2KB
    int v0[MAX_STR_LEN + 1];
    int v1[MAX_STR_LEN + 1];

    // 初始化第一行
    for (int i = 0; i <= len2; i++) v0[i] = i;

    for (int i = 0; i < len1; i++) {
        v1[0] = i + 1;
        for (int j = 0; j < len2; j++) {
            int cost = (s1[i] == s2[j]) ? 0 : 1;
            v1[j + 1] = MIN3(
                v1[j] + 1,       // insertion
                v0[j + 1] + 1,   // deletion
                v0[j] + cost     // substitution
            );
        }
        // 将 v1 复制到 v0，为下一轮做准备
        memcpy(v0, v1, (len2 + 1) * sizeof(int));
    }

    return v0[len2];
}

int calculate_score(const char* user_ans, const char* correct_ans, int full_score) {
    if (!user_ans || !correct_ans) {
        LOG_ERROR("Invalid arguments to calculate_score");
        return 0;
    }

    char u_norm[MAX_STR_LEN + 1]; // +1 for safety
    char c_norm[MAX_STR_LEN + 1];

    // 1. 预处理：标准化 (转小写、去首尾空格、合并中间空格)
    normalize_string(u_norm, user_ans, sizeof(u_norm));
    normalize_string(c_norm, correct_ans, sizeof(c_norm));

    // 2. 精确匹配 (标准化后)
    if (strcmp(u_norm, c_norm) == 0) {
        return full_score;
    }

    // 3. 模糊匹配 (Fuzzy Matching)
    int len = strlen(c_norm);
    int dist = levenshtein_distance(u_norm, c_norm);

    // 智能容错规则：
    // - 长度 <= 3: 必须精确匹配 (dist == 0)
    // - 长度 4-10: 允许 1 个字符差异 (如打字错误)
    // - 长度 > 10: 允许 20% 的编辑距离误差 (如长句子中的个别错词)
    int allowed_errors = 0;
    if (len <= 3) {
        allowed_errors = 0;
    } else if (len <= 10) {
        allowed_errors = 1;
    } else {
        allowed_errors = (int)(len * 0.2); 
    }

    // 额外保护：如果编辑距离过大（超过长度的一半），直接判错
    // 防止短字符串匹配到完全无关的长字符串
    if (dist > len / 2) {
        return 0;
    }

    if (dist <= allowed_errors) {
        return full_score;
    }

    return 0;
}