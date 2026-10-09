using Nexus.PLM.Addin.Sdk.Translators;
using SkiaSharp;

namespace Nexus.PLM.Inkscape.Translators;

/// <summary>Renders an Inkscape SVG drawing to a JPEG over a white background.</summary>
public sealed class SvgToJpegTranslator : ITranslator
{
    /// <inheritdoc/>
    public string Key => "svg_to_jpeg";

    /// <inheritdoc/>
    public string Label => "SVG → JPEG";

    /// <inheritdoc/>
    public string Description =>
        "Renders an SVG drawing to a JPEG over a white background (JPEG carries no transparency). Pure .NET — no Inkscape needed on the server.";

    /// <inheritdoc/>
    public string InputMimeType => MimeTypes.Svg;

    /// <inheritdoc/>
    public string OutputMimeType => MimeTypes.Jpeg;

    /// <inheritdoc/>
    public string OutputFileExtension => ".jpg";

    /// <inheritdoc/>
    public Task<Stream> TranslateAsync(Stream input, CancellationToken cancellationToken = default)
    {
        using var svg = SvgRenderer.Load(input);
        using var bitmap = SvgRenderer.ToBitmap(svg, SKColors.White);
        using var image = SKImage.FromBitmap(bitmap);
        using var data = image.Encode(SKEncodedImageFormat.Jpeg, 90);
        return Task.FromResult<Stream>(new MemoryStream(data.ToArray()));
    }
}
