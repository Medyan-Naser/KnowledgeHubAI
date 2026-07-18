const API_BASE = '/api/v1';

async function safeJson(res) {
  const text = await res.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

export async function checkHealth() {
  try {
    const res = await fetch(`${API_BASE}/health`);
    return await safeJson(res) || { status: 'error' };
  } catch (e) {
    return { status: 'error', error: e.message };
  }
}

export async function uploadDocument(file) {
  const formData = new FormData();
  formData.append('file', file);
  
  const res = await fetch(`${API_BASE}/documents`, {
    method: 'POST',
    body: formData,
  });
  
  const data = await safeJson(res);
  
  if (!res.ok) {
    throw new Error(data?.detail || 'Upload failed');
  }
  
  return data;
}

export async function getDocuments() {
  try {
    const res = await fetch(`${API_BASE}/documents`);
    if (!res.ok) throw new Error('Failed to fetch documents');
    const data = await safeJson(res);
    return data?.documents || [];
  } catch (e) {
    console.error('getDocuments error:', e);
    return [];
  }
}

export async function deleteDocument(id) {
  const res = await fetch(`${API_BASE}/documents/${id}`, {
    method: 'DELETE',
  });
  const data = await safeJson(res);
  if (!res.ok) throw new Error(data?.detail || 'Failed to delete document');
  return data;
}

export async function sendChatMessage(query) {
  const res = await fetch(`${API_BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query }),
  });
  
  const data = await safeJson(res);
  
  if (!res.ok) {
    throw new Error(data?.detail || 'Chat request failed');
  }
  
  if (!data) {
    throw new Error('Empty response from server');
  }
  
  return data;
}
