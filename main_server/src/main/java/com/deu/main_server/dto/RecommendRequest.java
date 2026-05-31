package com.deu.main_server.dto;

import java.util.List;

public record RecommendRequest(String department, List<String> history) {
}