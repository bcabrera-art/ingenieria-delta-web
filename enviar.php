<?php
/**
 * Script de envío directo de cotizaciones para ingenieriadelta.cl
 * Envía las solicitudes (y adjuntos PDF/imagen) simultáneamente a
 * bcabrera@ingenieriadelta.cl y cdiaz@ingenieriadelta.cl.
 * Compatible con cPanel / PHP estándar (JSON y multipart/form-data).
 */
header('Content-Type: application/json; charset=utf-8');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type, Accept');

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(200);
    exit;
}

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(405);
    echo json_encode(['ok' => false, 'message' => 'Método no permitido. Usa POST.']);
    exit;
}

// Leer datos JSON o multipart/form-data / form-urlencoded
$data = $_POST;
if (empty($data)) {
    $rawInput = file_get_contents('php://input');
    $jsonInput = json_decode($rawInput, true);
    if (is_array($jsonInput)) {
        $data = $jsonInput;
    }
}

// Honeypot anti-spam
if (!empty($data['website_hp'])) {
    echo json_encode(['ok' => true, 'message' => 'Enviado correctamente']);
    exit;
}

$cleanInline = static function ($value): string {
    return trim(str_replace(["\r", "\n"], ' ', strip_tags((string)$value)));
};

$nombre            = $cleanInline($data['nombre'] ?? '');
$empresa           = $cleanInline($data['empresa'] ?? 'Particular / Hogar');
$correo            = filter_var(trim(str_replace(["\r", "\n"], '', (string)($data['correo'] ?? ''))), FILTER_SANITIZE_EMAIL);
$telefono          = $cleanInline($data['telefono'] ?? '');
$ubicacion         = $cleanInline($data['ubicacion'] ?? 'Región de Aysén');
$linea             = $cleanInline($data['linea'] ?? '');
$consumo           = $cleanInline($data['consumo'] ?? '');
$potenciaGenerador = $cleanInline($data['potencia_generador'] ?? '');
$faseGenerador     = $cleanInline($data['fase_generador'] ?? '');
$tipo              = $cleanInline($data['tipo'] ?? '');
$origen            = $cleanInline($data['origen'] ?? 'directo');

$servicios = $data['servicios'] ?? [];
if (is_array($servicios)) {
    $serviciosStr = implode(', ', array_map($cleanInline, $servicios));
} else {
    $serviciosStr = $cleanInline($servicios);
}
$simulacion = trim(strip_tags((string)($data['simulacion'] ?? 'No especificada')));
$mensaje    = trim(strip_tags((string)($data['mensaje'] ?? '')));

if (empty($nombre) || empty($correo) || !filter_var($correo, FILTER_VALIDATE_EMAIL)) {
    http_response_code(400);
    echo json_encode([
        'ok' => false,
        'message' => 'Por favor ingresa un nombre válido y un correo electrónico correcto.'
    ]);
    exit;
}

// Validación y preparación de archivos adjuntos opcionales
$maxFileBytes = 10 * 1024 * 1024;
$attachments  = [];

$detectMime = static function (string $tmpPath, string $clientMime): string {
    if (class_exists('finfo')) {
        $finfo = new finfo(FILEINFO_MIME_TYPE);
        $detected = $finfo->file($tmpPath);
        if (is_string($detected) && $detected !== '') {
            return strtolower($detected);
        }
    }
    return strtolower($clientMime);
};

$sanitizeFilename = static function (string $name, string $fallback): string {
    $base = basename(str_replace(["\r", "\n", '"', '\\'], '', $name));
    $clean = preg_replace('/[^A-Za-z0-9._-]/', '_', $base);
    return $clean !== '' ? $clean : $fallback;
};

if (isset($_FILES['boleta_pdf']) && ($_FILES['boleta_pdf']['error'] ?? UPLOAD_ERR_NO_FILE) !== UPLOAD_ERR_NO_FILE) {
    $file = $_FILES['boleta_pdf'];
    if (($file['error'] ?? UPLOAD_ERR_OK) !== UPLOAD_ERR_OK) {
        http_response_code(422);
        echo json_encode(['ok' => false, 'error' => 'No se pudo procesar la boleta en PDF adjunta.']);
        exit;
    }
    $origName = (string)($file['name'] ?? '');
    $ext = strtolower(pathinfo($origName, PATHINFO_EXTENSION));
    $mime = $detectMime((string)$file['tmp_name'], (string)($file['type'] ?? ''));
    if (($file['size'] ?? 0) > $maxFileBytes || $ext !== 'pdf' || !in_array($mime, ['application/pdf', 'application/x-pdf'], true)) {
        http_response_code(422);
        echo json_encode(['ok' => false, 'error' => 'Solo se permite adjuntar la cuenta eléctrica en formato PDF (.pdf).']);
        exit;
    }
    $content = @file_get_contents((string)$file['tmp_name']);
    if ($content !== false) {
        $attachments[] = [
            'filename' => $sanitizeFilename($origName, 'cuenta_electrica.pdf'),
            'mime' => 'application/pdf',
            'content' => $content
        ];
    }
}

if (isset($_FILES['foto_generador']) && ($_FILES['foto_generador']['error'] ?? UPLOAD_ERR_NO_FILE) !== UPLOAD_ERR_NO_FILE) {
    $file = $_FILES['foto_generador'];
    if (($file['error'] ?? UPLOAD_ERR_OK) !== UPLOAD_ERR_OK) {
        http_response_code(422);
        echo json_encode(['ok' => false, 'error' => 'No se pudo procesar la fotografía del generador.']);
        exit;
    }
    $origName = (string)($file['name'] ?? '');
    $ext = strtolower(pathinfo($origName, PATHINFO_EXTENSION));
    $mime = $detectMime((string)$file['tmp_name'], (string)($file['type'] ?? ''));
    $allowedImgExt  = ['jpg', 'jpeg', 'png', 'webp', 'heic', 'heif'];
    $allowedImgMime = ['image/jpeg', 'image/pjpeg', 'image/png', 'image/webp', 'image/heic', 'image/heif'];
    if (($file['size'] ?? 0) > $maxFileBytes || !in_array($ext, $allowedImgExt, true) || !in_array($mime, $allowedImgMime, true)) {
        http_response_code(422);
        echo json_encode(['ok' => false, 'error' => 'La fotografía del generador debe ser JPG, PNG, WEBP o HEIC (máx. 10 MB).']);
        exit;
    }
    $content = @file_get_contents((string)$file['tmp_name']);
    if ($content !== false) {
        $attachments[] = [
            'filename' => $sanitizeFilename($origName, 'generador.' . $ext),
            'mime' => $mime,
            'content' => $content
        ];
    }
}

// Destinatarios oficiales de Ingeniería Delta
$destinatarios = 'bcabrera@ingenieriadelta.cl, cdiaz@ingenieriadelta.cl';
$asunto = "Nueva Cotización Web - $nombre ($ubicacion) | Ingeniería Delta";

$cuerpo = "========================================================\n";
$cuerpo .= " NUEVA SOLICITUD DE COTIZACIÓN - INGENIERIADELTA.CL\n";
$cuerpo .= "========================================================\n\n";
$cuerpo .= "Nombre completo : $nombre\n";
$cuerpo .= "Tipo / Empresa  : $empresa\n";
$cuerpo .= "Correo          : $correo\n";
$cuerpo .= "Teléfono        : $telefono\n";
$cuerpo .= "Ubicación       : $ubicacion\n";
$cuerpo .= "Situación       : " . ($serviciosStr ?: 'Consulta General') . "\n";
if ($consumo !== '') {
    $cuerpo .= "Consumo / Gasto : $consumo\n";
}
if ($potenciaGenerador !== '') {
    $cuerpo .= "Potencia Gen.   : $potenciaGenerador\n";
}
if ($faseGenerador !== '') {
    $cuerpo .= "Fase Generador  : $faseGenerador\n";
}
if ($tipo !== '') {
    $cuerpo .= "Lugar / Uso     : $tipo\n";
}
if (!empty($attachments)) {
    $names = array_map(static fn($a) => $a['filename'], $attachments);
    $cuerpo .= "Adjuntos        : " . implode(', ', $names) . "\n";
}
$cuerpo .= "Origen CTA      : $origen\n\n";
$cuerpo .= "--- DATOS DEL SIMULADOR SOLAR DELTA AYSÉN (610 Wp) ---\n";
$cuerpo .= "$simulacion\n\n";
$cuerpo .= "--- MENSAJE / DETALLES DEL PROYECTO ---\n";
$cuerpo .= ($mensaje ?: 'Sin comentarios adicionales.') . "\n\n";
$cuerpo .= "--------------------------------------------------------\n";
$cuerpo .= "Enviado desde: https://ingenieriadelta.cl/\n";
$cuerpo .= "Fecha: " . date('d/m/Y H:i:s') . "\n";

$headers = [];
$headers[] = 'MIME-Version: 1.0';
$headers[] = 'From: Web Ingeniería Delta <no-responder@ingenieriadelta.cl>';
$headers[] = 'Reply-To: ' . $nombre . ' <' . $correo . '>';
$headers[] = 'X-Mailer: PHP/' . phpversion();

if (empty($attachments)) {
    $headers[] = 'Content-Type: text/plain; charset=UTF-8';
    $mailBody = $cuerpo;
} else {
    $boundary = '==DeltaBoundary_' . bin2hex(random_bytes(12));
    $headers[] = 'Content-Type: multipart/mixed; boundary="' . $boundary . '"';

    $mailBody  = "--{$boundary}\r\n";
    $mailBody .= "Content-Type: text/plain; charset=UTF-8\r\n";
    $mailBody .= "Content-Transfer-Encoding: 8bit\r\n\r\n";
    $mailBody .= $cuerpo . "\r\n\r\n";

    foreach ($attachments as $att) {
        $mailBody .= "--{$boundary}\r\n";
        $mailBody .= 'Content-Type: ' . $att['mime'] . '; name="' . $att['filename'] . "\"\r\n";
        $mailBody .= "Content-Transfer-Encoding: base64\r\n";
        $mailBody .= 'Content-Disposition: attachment; filename="' . $att['filename'] . "\"\r\n\r\n";
        $mailBody .= chunk_split(base64_encode($att['content'])) . "\r\n";
    }
    $mailBody .= "--{$boundary}--\r\n";
}

$enviado = @mail($destinatarios, '=?UTF-8?B?' . base64_encode($asunto) . '?=', $mailBody, implode("\r\n", $headers));

if ($enviado) {
    echo json_encode([
        'ok' => true,
        'attachments' => count($attachments),
        'message' => 'Tu solicitud fue enviada directamente a bcabrera@ingenieriadelta.cl y cdiaz@ingenieriadelta.cl.'
    ]);
} else {
    // Si se ejecuta en entorno local sin servidor SMTP activo, informa al frontend para activar el respaldo directo
    http_response_code(202);
    echo json_encode([
        'ok' => false,
        'fallback' => true,
        'message' => 'Usando pasarela de correo en la nube de respaldo.'
    ]);
}
