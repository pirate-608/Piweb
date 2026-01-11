#include "common.h"

void get_user_input(char* buffer, int size) {
    if (!buffer || size <= 0) {
        LOG_ERROR("Invalid arguments to get_user_input");
        return;
    }

    if (fgets(buffer, size, stdin) != NULL) {
        size_t len = strlen(buffer);
        if (len > 0 && buffer[len - 1] == '\n') {
            buffer[len - 1] = '\0';
        }
    } else {
        if (ferror(stdin)) {
            LOG_ERROR("Error reading from stdin");
        }
        buffer[0] = '\0';
    }
}
