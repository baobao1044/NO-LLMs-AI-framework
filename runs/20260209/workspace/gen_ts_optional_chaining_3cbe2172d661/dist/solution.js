"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.pick_user_name = pick_user_name;
function pick_user_name(input) {
    return input?.user?.name ?? "";
}
