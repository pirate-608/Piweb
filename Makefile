CC = gcc
CFLAGS = -Wall -g -O2 -Iinclude -fPIC
OBJ = main.o get_data.o put_questions.o get_answer.o grading.o add_questions.o
BUILD_DIR = build

# Detect OS
ifeq ($(OS),Windows_NT)
    TARGET_EXT = .exe
    LIB_EXT = .dll
    RM = del /Q
    RMDIR = rmdir /S /Q
    MKDIR = if not exist $(BUILD_DIR) mkdir $(BUILD_DIR)
    CLEAN_CMD = if exist $(BUILD_DIR) $(RMDIR) $(BUILD_DIR)
else
    UNAME_S := $(shell uname -s)
    TARGET_EXT = 
    RM = rm -f
    RMDIR = rm -rf
    MKDIR = mkdir -p $(BUILD_DIR)
    CLEAN_CMD = $(RMDIR) $(BUILD_DIR)
    
    ifeq ($(UNAME_S),Darwin)
        LIB_EXT = .dylib
    else
        LIB_EXT = .so
    endif
endif

ifneq ($(OS),Windows_NT)
    UNAME_S := $(shell uname -s)
    
    # If Linux, link against math library securely
    ifeq ($(UNAME_S),Linux)
        LDFLAGS = -lm
    endif
endif

TARGET = $(BUILD_DIR)/auto_grader$(TARGET_EXT)
LIB_TARGET = $(BUILD_DIR)/libgrading$(LIB_EXT)

all: $(TARGET) $(LIB_TARGET)

$(TARGET): $(OBJ) | $(BUILD_DIR)
	$(CC) $(OBJ) -o $(TARGET) $(LDFLAGS)

$(LIB_TARGET): src/grading.c include/common.h | $(BUILD_DIR)
	$(CC) $(CFLAGS) -shared -o $(LIB_TARGET) src/grading.c -Iinclude $(LDFLAGS)

$(BUILD_DIR):
	$(MKDIR)

%.o: src/%.c include/common.h
	$(CC) $(CFLAGS) -c $< -o $@

clean:
	$(RM) *.o
	$(CLEAN_CMD)