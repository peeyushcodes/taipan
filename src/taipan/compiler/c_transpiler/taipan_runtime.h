#ifndef TAIPAN_RUNTIME_H
#define TAIPAN_RUNTIME_H

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdbool.h>
#include <math.h>
#include <stdarg.h>

typedef enum {
    VAL_NULL,
    VAL_BOOL,
    VAL_INT,
    VAL_FLOAT,
    VAL_STRING,
    VAL_LIST,
    VAL_RANGE,
    VAL_FUNCTION
} PeeValType;

struct PeeValue;
typedef struct PeeValue PeeValue;

typedef struct {
    PeeValue* data;
    int length;
    int capacity;
} PeeListVal;

typedef struct {
    long long start;
    long long end;
    long long step;
    bool inclusive;
} PeeRangeVal;

typedef PeeValue (*PeeCFunction)(int arg_count, PeeValue* args);

typedef struct {
    PeeCFunction func;
    const char* name;
} PeeFuncVal;

struct PeeValue {
    PeeValType type;
    union {
        bool bool_val;
        long long int_val;
        double float_val;
        char* string_val;
        PeeListVal* list_val;
        PeeRangeVal range_val;
        PeeFuncVal func_val;
    };
};

// Creators
static inline PeeValue pee_null() {
    PeeValue v; v.type = VAL_NULL; return v;
}
static inline PeeValue pee_bool(bool b) {
    PeeValue v; v.type = VAL_BOOL; v.bool_val = b; return v;
}
static inline PeeValue pee_int(long long i) {
    PeeValue v; v.type = VAL_INT; v.int_val = i; return v;
}
static inline PeeValue pee_float(double f) {
    PeeValue v; v.type = VAL_FLOAT; v.float_val = f; return v;
}
static inline PeeValue pee_string(const char* s) {
    PeeValue v; v.type = VAL_STRING; v.string_val = strdup(s); return v;
}
static inline PeeValue pee_range(long long start, long long end, long long step, bool inclusive) {
    PeeValue v; v.type = VAL_RANGE;
    v.range_val.start = start;
    v.range_val.end = end;
    v.range_val.step = step;
    v.range_val.inclusive = inclusive;
    return v;
}
static inline PeeValue pee_func(PeeCFunction f, const char* name) {
    PeeValue v; v.type = VAL_FUNCTION;
    v.func_val.func = f;
    v.func_val.name = name;
    return v;
}

// Truthiness
static inline bool pee_truthy(PeeValue v) {
    switch (v.type) {
        case VAL_NULL: return false;
        case VAL_BOOL: return v.bool_val;
        case VAL_INT: return v.int_val != 0;
        case VAL_FLOAT: return v.float_val != 0.0;
        case VAL_STRING: return strlen(v.string_val) > 0;
        case VAL_LIST: return v.list_val->length > 0;
        default: return true;
    }
}

// String Conversion
static inline char* pee_to_c_string(PeeValue v) {
    char buf[256];
    if (v.type == VAL_NULL) return strdup("null");
    if (v.type == VAL_BOOL) return strdup(v.bool_val ? "true" : "false");
    if (v.type == VAL_INT) {
        sprintf(buf, "%lld", v.int_val);
        return strdup(buf);
    }
    if (v.type == VAL_FLOAT) {
        sprintf(buf, "%g", v.float_val);
        return strdup(buf);
    }
    if (v.type == VAL_STRING) {
        return strdup(v.string_val);
    }
    if (v.type == VAL_LIST) {
        int len = v.list_val->length;
        if (len == 0) return strdup("[]");
        int cap = 128;
        char* res = malloc(cap);
        strcpy(res, "[");
        for (int i = 0; i < len; i++) {
            char* s = pee_to_c_string(v.list_val->data[i]);
            if (strlen(res) + strlen(s) + 5 >= cap) {
                cap = cap * 2 + strlen(s);
                res = realloc(res, cap);
            }
            strcat(res, s);
            free(s);
            if (i < len - 1) {
                strcat(res, ", ");
            }
        }
        strcat(res, "]");
        return res;
    }
    if (v.type == VAL_RANGE) {
        sprintf(buf, "%lld..%lld", v.range_val.start, v.range_val.end);
        return strdup(buf);
    }
    return strdup("<object>");
}

// Builtins
static inline PeeValue pee_str_fn(PeeValue v) {
    char* s = pee_to_c_string(v);
    PeeValue res = pee_string(s);
    free(s);
    return res;
}

static inline PeeValue pee_int_fn(PeeValue v) {
    if (v.type == VAL_INT) return v;
    if (v.type == VAL_FLOAT) return pee_int((long long)v.float_val);
    if (v.type == VAL_BOOL) return pee_int(v.bool_val ? 1 : 0);
    if (v.type == VAL_STRING) {
        return pee_int(atoll(v.string_val));
    }
    fprintf(stderr, "TypeError: Cannot convert to Int\n");
    exit(1);
}

static inline PeeValue pee_float_fn(PeeValue v) {
    if (v.type == VAL_FLOAT) return v;
    if (v.type == VAL_INT) return pee_float((double)v.int_val);
    if (v.type == VAL_BOOL) return pee_float(v.bool_val ? 1.0 : 0.0);
    if (v.type == VAL_STRING) {
        return pee_float(atof(v.string_val));
    }
    fprintf(stderr, "TypeError: Cannot convert to Float\n");
    exit(1);
}

static inline PeeValue pee_bool_fn(PeeValue v) {
    return pee_bool(pee_truthy(v));
}

static inline PeeValue pee_len_fn(PeeValue v) {
    if (v.type == VAL_STRING) return pee_int(strlen(v.string_val));
    if (v.type == VAL_LIST) return pee_int(v.list_val->length);
    fprintf(stderr, "TypeError: len() does not support this type\n");
    exit(1);
}

static inline PeeValue pee_input_fn(PeeValue prompt) {
    if (prompt.type == VAL_STRING) {
        printf("%s", prompt.string_val);
    } else if (prompt.type != VAL_NULL) {
        char* ps = pee_to_c_string(prompt);
        printf("%s", ps);
        free(ps);
    }
    fflush(stdout);
    char buf[2048];
    if (fgets(buf, sizeof(buf), stdin) == NULL) {
        return pee_string("");
    }
    size_t len = strlen(buf);
    if (len > 0 && buf[len - 1] == '\n') {
        buf[len - 1] = '\0';
    }
    return pee_string(buf);
}

static inline void pee_show(int count, ...) {
    va_list args;
    va_start(args, count);
    for (int i = 0; i < count; i++) {
        PeeValue v = va_arg(args, PeeValue);
        char* s = pee_to_c_string(v);
        printf("%s", s);
        free(s);
        if (i < count - 1) printf(" ");
    }
    printf("\n");
    va_end(args);
}

// Collections
static inline PeeValue pee_list_new() {
    PeeValue v;
    v.type = VAL_LIST;
    v.list_val = malloc(sizeof(PeeListVal));
    v.list_val->length = 0;
    v.list_val->capacity = 4;
    v.list_val->data = malloc(sizeof(PeeValue) * 4);
    return v;
}

static inline void pee_list_append(PeeValue list, PeeValue val) {
    if (list.type != VAL_LIST) return;
    PeeListVal* l = list.list_val;
    if (l->length >= l->capacity) {
        l->capacity *= 2;
        l->data = realloc(l->data, sizeof(PeeValue) * l->capacity);
    }
    l->data[l->length++] = val;
}

static inline PeeValue pee_index_get(PeeValue obj, PeeValue idx) {
    if (obj.type == VAL_LIST) {
        long long i = idx.int_val;
        if (i < 0) i += obj.list_val->length;
        if (i < 0 || i >= obj.list_val->length) {
            fprintf(stderr, "IndexError: List index out of range\n");
            exit(1);
        }
        return obj.list_val->data[i];
    }
    if (obj.type == VAL_STRING) {
        long long i = idx.int_val;
        long long len = strlen(obj.string_val);
        if (i < 0) i += len;
        if (i < 0 || i >= len) {
            fprintf(stderr, "IndexError: String index out of range\n");
            exit(1);
        }
        char char_str[2] = { obj.string_val[i], '\0' };
        return pee_string(char_str);
    }
    fprintf(stderr, "TypeError: Object not subscriptable\n");
    exit(1);
}

static inline void pee_index_set(PeeValue obj, PeeValue idx, PeeValue val) {
    if (obj.type == VAL_LIST) {
        long long i = idx.int_val;
        if (i < 0) i += obj.list_val->length;
        if (i < 0 || i >= obj.list_val->length) {
            fprintf(stderr, "IndexError: List index out of range\n");
            exit(1);
        }
        obj.list_val->data[i] = val;
        return;
    }
    fprintf(stderr, "TypeError: Object does not support item assignment\n");
    exit(1);
}

// Operators
static inline PeeValue pee_add(PeeValue a, PeeValue b) {
    if (a.type == VAL_STRING || b.type == VAL_STRING) {
        char* sa = pee_to_c_string(a);
        char* sb = pee_to_c_string(b);
        char* res = malloc(strlen(sa) + strlen(sb) + 1);
        strcpy(res, sa);
        strcat(res, sb);
        free(sa);
        free(sb);
        PeeValue v;
        v.type = VAL_STRING;
        v.string_val = res;
        return v;
    }
    if (a.type == VAL_INT && b.type == VAL_INT) {
        return pee_int(a.int_val + b.int_val);
    }
    if ((a.type == VAL_INT || a.type == VAL_FLOAT) && (b.type == VAL_INT || b.type == VAL_FLOAT)) {
        double va = (a.type == VAL_INT) ? (double)a.int_val : a.float_val;
        double vb = (b.type == VAL_INT) ? (double)b.int_val : b.float_val;
        return pee_float(va + vb);
    }
    if (a.type == VAL_LIST && b.type == VAL_LIST) {
        PeeValue res = pee_list_new();
        for (int i = 0; i < a.list_val->length; i++) {
            pee_list_append(res, a.list_val->data[i]);
        }
        for (int i = 0; i < b.list_val->length; i++) {
            pee_list_append(res, b.list_val->data[i]);
        }
        return res;
    }
    fprintf(stderr, "TypeError: Operator '+' cannot be applied to these types\n");
    exit(1);
}

static inline PeeValue pee_sub(PeeValue a, PeeValue b) {
    if (a.type == VAL_INT && b.type == VAL_INT) return pee_int(a.int_val - b.int_val);
    if ((a.type == VAL_INT || a.type == VAL_FLOAT) && (b.type == VAL_INT || b.type == VAL_FLOAT)) {
        double va = (a.type == VAL_INT) ? (double)a.int_val : a.float_val;
        double vb = (b.type == VAL_INT) ? (double)b.int_val : b.float_val;
        return pee_float(va - vb);
    }
    fprintf(stderr, "TypeError: Operator '-' cannot be applied to these types\n");
    exit(1);
}

static inline PeeValue pee_mul(PeeValue a, PeeValue b) {
    if (a.type == VAL_STRING && b.type == VAL_INT) {
        long long times = b.int_val;
        if (times < 0) times = 0;
        char* sa = a.string_val;
        char* res = malloc(strlen(sa) * times + 1);
        res[0] = '\0';
        for (long long i = 0; i < times; i++) {
            strcat(res, sa);
        }
        PeeValue v; v.type = VAL_STRING; v.string_val = res;
        return v;
    }
    if (a.type == VAL_INT && b.type == VAL_INT) return pee_int(a.int_val * b.int_val);
    if ((a.type == VAL_INT || a.type == VAL_FLOAT) && (b.type == VAL_INT || b.type == VAL_FLOAT)) {
        double va = (a.type == VAL_INT) ? (double)a.int_val : a.float_val;
        double vb = (b.type == VAL_INT) ? (double)b.int_val : b.float_val;
        return pee_float(va * vb);
    }
    fprintf(stderr, "TypeError: Operator '*' cannot be applied to these types\n");
    exit(1);
}

static inline PeeValue pee_div(PeeValue a, PeeValue b) {
    double va = (a.type == VAL_INT) ? (double)a.int_val : a.float_val;
    double vb = (b.type == VAL_INT) ? (double)b.int_val : b.float_val;
    if (vb == 0.0) {
        fprintf(stderr, "DivisionByZeroError\n");
        exit(1);
    }
    return pee_float(va / vb);
}

static inline PeeValue pee_mod(PeeValue a, PeeValue b) {
    if (a.type == VAL_INT && b.type == VAL_INT) {
        if (b.int_val == 0) {
            fprintf(stderr, "DivisionByZeroError\n");
            exit(1);
        }
        return pee_int(a.int_val % b.int_val);
    }
    fprintf(stderr, "TypeError: Operator '%%' cannot be applied to these types\n");
    exit(1);
}

static inline PeeValue pee_pow(PeeValue a, PeeValue b) {
    double va = (a.type == VAL_INT) ? (double)a.int_val : a.float_val;
    double vb = (b.type == VAL_INT) ? (double)b.int_val : b.float_val;
    return pee_float(pow(va, vb));
}

static inline PeeValue pee_neg(PeeValue a) {
    if (a.type == VAL_INT) return pee_int(-a.int_val);
    if (a.type == VAL_FLOAT) return pee_float(-a.float_val);
    fprintf(stderr, "TypeError: Operator '-' cannot be applied to this type\n");
    exit(1);
}

static inline bool pee_eq_c(PeeValue a, PeeValue b) {
    if (a.type != b.type) {
        if ((a.type == VAL_INT || a.type == VAL_FLOAT) && (b.type == VAL_INT || b.type == VAL_FLOAT)) {
            double va = (a.type == VAL_INT) ? (double)a.int_val : a.float_val;
            double vb = (b.type == VAL_INT) ? (double)b.int_val : b.float_val;
            return va == vb;
        }
        return false;
    }
    switch (a.type) {
        case VAL_NULL: return true;
        case VAL_BOOL: return a.bool_val == b.bool_val;
        case VAL_INT: return a.int_val == b.int_val;
        case VAL_FLOAT: return a.float_val == b.float_val;
        case VAL_STRING: return strcmp(a.string_val, b.string_val) == 0;
        case VAL_LIST: {
            if (a.list_val->length != b.list_val->length) return false;
            for (int i = 0; i < a.list_val->length; i++) {
                if (!pee_eq_c(a.list_val->data[i], b.list_val->data[i])) return false;
            }
            return true;
        }
        default: return false;
    }
}

static inline PeeValue pee_eq(PeeValue a, PeeValue b) { return pee_bool(pee_eq_c(a, b)); }
static inline PeeValue pee_ne(PeeValue a, PeeValue b) { return pee_bool(!pee_eq_c(a, b)); }

static inline int pee_compare(PeeValue a, PeeValue b) {
    if ((a.type == VAL_INT || a.type == VAL_FLOAT) && (b.type == VAL_INT || b.type == VAL_FLOAT)) {
        double va = (a.type == VAL_INT) ? (double)a.int_val : a.float_val;
        double vb = (b.type == VAL_INT) ? (double)b.int_val : b.float_val;
        if (va < vb) return -1;
        if (va > vb) return 1;
        return 0;
    }
    if (a.type == VAL_STRING && b.type == VAL_STRING) {
        return strcmp(a.string_val, b.string_val);
    }
    fprintf(stderr, "TypeError: Cannot compare these types\n");
    exit(1);
}

static inline PeeValue pee_lt(PeeValue a, PeeValue b) { return pee_bool(pee_compare(a, b) < 0); }
static inline PeeValue pee_le(PeeValue a, PeeValue b) { return pee_bool(pee_compare(a, b) <= 0); }
static inline PeeValue pee_gt(PeeValue a, PeeValue b) { return pee_bool(pee_compare(a, b) > 0); }
static inline PeeValue pee_ge(PeeValue a, PeeValue b) { return pee_bool(pee_compare(a, b) >= 0); }

// Dynamic Call
static inline PeeValue pee_call_dynamic(PeeValue func_val, int arg_count, ...) {
    if (func_val.type != VAL_FUNCTION) {
        fprintf(stderr, "TypeError: Object is not callable\n");
        exit(1);
    }
    va_list args;
    va_start(args, arg_count);
    PeeValue* arg_array = malloc(sizeof(PeeValue) * (arg_count > 0 ? arg_count : 1));
    for (int i = 0; i < arg_count; i++) {
        arg_array[i] = va_arg(args, PeeValue);
    }
    PeeValue res = func_val.func_val.func(arg_count, arg_array);
    free(arg_array);
    va_end(args);
    return res;
}

#endif // TAIPAN_RUNTIME_H
