using Nexus.PLM.Addin.Sdk.Translators;
using SkiaSharp;

namespace Nexus.PLM.Inkscape.Translators;

/// <summary>Renders an Inkscape SVG drawing to a PNG, keeping transparency.</summary>
public sealed class SvgToPngTranslator : ITranslator
{
    /// <inheritdoc/>
    public string Key => "svg_to_png";

    /// <inheritdoc/>
    public string Label => "SVG → PNG";

    /// <inheritdoc/>
    public string Description =>
        "Renders an SVG drawing to a PNG raster at its natural size, transparency preserved. Pure .NET — no Inkscape needed on the server.";

    /// <inheritdoc/>
    public string InputMimeType => MimeTypes.Svg;

    /// <inheritdoc/>
    public string OutputMimeType => MimeTypes.Png;

    /// <inheritdoc/>
    public string OutputFileExtension => ".png";

    /// <inheritdoc/>
    public Task<Stream> TranslateAsync(Stream input, CancellationToken cancellationToken = default)
    {
        using var svg = SvgRenderer.Load(input);
        using var bitmap = SvgRenderer.ToBitmap(svg, SKColors.Transparent);
        using var image = SKImage.FromBitmap(bitmap);
        using var data = image.Encode(SKEncodedImageFormat.Png, 100);
        return Task.FromResult<Stream>(new MemoryStream(data.ToArray()));
    }
}
