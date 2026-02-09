"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.union_to_number = union_to_number;
function union_to_number(value) {
    if (typeof value === "string") {
        return Number(value);
    }
    return value;
}
