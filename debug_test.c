#include <stdio.h>
#include <stdlib.h>

#define NO_INLINE __attribute__((noinline))

NO_INLINE void check_null_logic(int *p) {
    int val = *p;
    if (p == NULL) {
        printf("This code is a 'Time Bomb' and will be deleted at -O2.\n");
        return;
    }
    printf("Value: %d\n", val);
}

NO_INLINE int check_overflow_logic(int a) {
    int next = a + 1;
    if (next > a) {
        return 1;
    } else {
        return 0; 
    }
}

NO_INLINE void check_boundary_logic(int index) {
    int buffer[5] = {1, 2, 3, 4, 5};
    int val = buffer[index];
    if (index >= 5) {
        printf("Index out of bounds! (Optimizer may prune this).\n");
    }
    printf("Val: %d\n", val);
}

int main(int argc, char** argv) {
    int x = 10;
    check_null_logic(&x);
    check_overflow_logic(2000);
    check_boundary_logic(2);
    return 0;
}
