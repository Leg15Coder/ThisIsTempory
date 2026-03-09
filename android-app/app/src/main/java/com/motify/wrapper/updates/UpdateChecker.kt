package com.motify.wrapper.updates

import com.google.gson.Gson
import com.motify.wrapper.BuildConfig
import okhttp3.OkHttpClient
import okhttp3.Request

data class VersionInfo(
    val latest_version: String? = null,
    val minimum_supported_version: String? = null,
    val store_url: String? = null,
    val update_message: String? = null
)

class UpdateChecker(
    private val client: OkHttpClient = OkHttpClient(),
    private val gson: Gson = Gson()
) {
    fun check(): VersionInfo? {
        val request = Request.Builder().url(BuildConfig.UPDATE_CHECK_URL).build()
        client.newCall(request).execute().use { response ->
            if (!response.isSuccessful) return null
            val body = response.body?.string() ?: return null
            return gson.fromJson(body, VersionInfo::class.java)
        }
    }
}

