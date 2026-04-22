#ifndef UB_COMPAT_STDLIB_H
#define UB_COMPAT_STDLIB_H

#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

#define EXIT_SUCCESS 0
#define EXIT_FAILURE 1
#define RAND_MAX 32767

int abs(int x);
long labs(long x);
long long llabs(long long x);

double atof(const char *nptr);
int atoi(const char *nptr);
long atol(const char *nptr);
long long atoll(const char *nptr);

void *malloc(size_t size);
void *calloc(size_t nmemb, size_t size);
void *realloc(void *ptr, size_t size);
void free(void *ptr);

void abort(void);
void exit(int status);

int rand(void);
void srand(unsigned int seed);

#ifdef __cplusplus
}
#endif

#endif