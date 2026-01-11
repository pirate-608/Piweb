cmake_minimum_required(VERSION 3.10)
project(auto_grader C)

set(CMAKE_C_STANDARD 99)

include_directories(include)
file(GLOB SRC_FILES src/*.c)

add_executable(auto_grader_cli ${SRC_FILES})
set_target_properties(auto_grader_cli PROPERTIES RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/build)

add_library(grading SHARED src/grading.c)
set_target_properties(grading PROPERTIES LIBRARY_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/build)
