package com.motify.wrapper.auth
}
    }
        }
            true
            cookieManager.flush()
            setCookies.forEach { cookieManager.setCookie(BuildConfig.BASE_URL, it) }
            val cookieManager = CookieManager.getInstance()
            val setCookies = response.headers("Set-Cookie")
            if (!response.isSuccessful) return@withContext false
        okHttpClient.newCall(request).execute().use { response ->

            .build()
            .post(body)
            .url("${BuildConfig.BASE_URL}/auth/google")
        val request = Request.Builder()

            .toRequestBody("application/json".toMediaType())
        val body = JSONObject().put("id_token", token).toString()
        val token = user.getIdToken(true).await().token ?: return@withContext false
        val user = FirebaseAuth.getInstance().currentUser ?: return@withContext false
    suspend fun syncFirebaseSession(): Boolean = withContext(Dispatchers.IO) {
) {
    private val okHttpClient: OkHttpClient = OkHttpClient()
    private val context: Context,
class SessionSyncManager(

import org.json.JSONObject
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.Request
import okhttp3.OkHttpClient
import okhttp3.MediaType.Companion.toMediaType
import kotlinx.coroutines.withContext
import kotlinx.coroutines.tasks.await
import kotlinx.coroutines.Dispatchers
import com.motify.wrapper.BuildConfig
import com.google.firebase.auth.FirebaseAuth
import android.webkit.CookieManager
import android.content.Context


