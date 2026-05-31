package com.deu.main_server.dto;

import java.util.List;

public record RecommendResponse(List<RecommendItem> recommendations) {
}