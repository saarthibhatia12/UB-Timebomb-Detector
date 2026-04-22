#ifndef UB_COMPAT_STDDEF_H
#define UB_COMPAT_STDDEF_H

#ifndef NULL
#ifdef __cplusplus
#define NULL nullptr
#else
#define NULL ((void*)0)
#endif
#endif

#ifndef UB_COMPAT_SIZE_T_DEFINED
#define UB_COMPAT_SIZE_T_DEFINED
typedef __SIZE_TYPE__ size_t;
#endif

#ifndef UB_COMPAT_PTRDIFF_T_DEFINED
#define UB_COMPAT_PTRDIFF_T_DEFINED
typedef __PTRDIFF_TYPE__ ptrdiff_t;
#endif

#ifndef __cplusplus
#ifndef UB_COMPAT_WCHAR_T_DEFINED
#define UB_COMPAT_WCHAR_T_DEFINED
typedef __WCHAR_TYPE__ wchar_t;
#endif
#endif

#ifndef UB_COMPAT_MAX_ALIGN_T_DEFINED
#define UB_COMPAT_MAX_ALIGN_T_DEFINED
typedef long double max_align_t;
#endif

#ifndef offsetof
#define offsetof(type, member) __builtin_offsetof(type, member)
#endif

#endif